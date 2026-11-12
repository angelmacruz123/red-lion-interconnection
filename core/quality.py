"""
core/quality.py
===============
Módulo 6 — Auditoría de seguridad del repositorio y cálculo del
**porcentaje de confianza** del sistema.

    Confianza (%) = 60 % × tasa de pruebas superadas
                  + 25 % × controles de seguridad cumplidos
                  + 15 % × cobertura de categorías (módulos con pruebas que pasan)

El reporte se escribe en `docs/pruebas.md` (entregable del Corte 3).
Se puede ejecutar desde la UI (Módulo 6) o por consola:
    python scripts/generate_test_report.py
"""

from __future__ import annotations

import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

WEIGHT_TESTS, WEIGHT_SECURITY, WEIGHT_COVERAGE = 0.60, 0.25, 0.15

CATEGORIES = {
    "test_ipam": "M2 · Planificación IP",
    "test_topology": "M3 · Topología",
    "test_topology_io": "M3 · Carga de topología",
    "test_generators": "M4 · Configuraciones multi-marca",
    "test_netdevops": "M5 · Consola NetDevOps",
    "test_deploy": "M5 · Despliegue a equipos",
    "test_serial": "M5 · Consola serial (COM)",
    "test_validators": "M6 · Validación de entradas",
    "test_security": "M6 · Anti-fuga de credenciales",
    "test_security_audit": "M6 · Configuraciones inseguras",
    "test_app": "UI · Streamlit (AppTest)",
}

# Patrones de secretos "hardcodeados" en el código fuente.
_SECRET_PATTERNS = [
    re.compile(r"""(?i)\b(password|passwd|secret|psk|api[_-]?key|token)\s*=\s*["'][^"'<\s]{6,}["']"""),
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key
]
_SCAN_EXCLUDE = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "configs_out", "tests"}


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


@dataclass
class TestCase:
    category: str
    name: str
    ok: bool
    message: str = ""


@dataclass
class QualityReport:
    tests: list[TestCase] = field(default_factory=list)
    checks: list[Check] = field(default_factory=list)
    duration_s: float = 0.0
    generated_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))

    @property
    def pass_rate(self) -> float:
        return sum(t.ok for t in self.tests) / len(self.tests) if self.tests else 0.0

    @property
    def security_score(self) -> float:
        return sum(c.ok for c in self.checks) / len(self.checks) if self.checks else 0.0

    @property
    def coverage_score(self) -> float:
        covered = {t.category for t in self.tests if t.ok}
        return len(covered & set(CATEGORIES)) / len(CATEGORIES)

    @property
    def confidence(self) -> float:
        return round(100 * (WEIGHT_TESTS * self.pass_rate + WEIGHT_SECURITY * self.security_score
                            + WEIGHT_COVERAGE * self.coverage_score), 1)

    def by_category(self) -> dict[str, tuple[int, int]]:
        out: dict[str, tuple[int, int]] = {}
        for t in self.tests:
            ok, total = out.get(t.category, (0, 0))
            out[t.category] = (ok + int(t.ok), total + 1)
        return out


# --------------------------------------------------------------------------- #
# Controles de seguridad del repositorio
# --------------------------------------------------------------------------- #


def scan_hardcoded_secrets(root: Path = ROOT) -> list[str]:
    hits = []
    for path in root.rglob("*"):
        if any(part in _SCAN_EXCLUDE for part in path.parts) or not path.is_file():
            continue
        if path.suffix not in {".py", ".toml", ".yaml", ".yml", ".json", ".cfg", ".ini", ".txt"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if any(p.search(line) for p in _SECRET_PATTERNS):
                hits.append(f"{path.relative_to(root)}:{lineno}")
    return hits


def security_checks(root: Path = ROOT) -> list[Check]:
    checks: list[Check] = []
    gi = root / ".gitignore"
    gi_text = gi.read_text(encoding="utf-8") if gi.exists() else ""
    gi_lines = {ln.strip() for ln in gi_text.splitlines()}
    checks.append(Check(".gitignore existe", gi.exists(), str(gi.name)))
    checks.append(Check(".env excluido por .gitignore", ".env" in gi_lines or ".env*" in gi_lines,
                        "Entrada '.env' en .gitignore"))
    checks.append(Check("Salidas de configuración excluidas", "configs_out/" in gi_lines,
                        "configs_out/ puede contener secretos sustituidos"))
    checks.append(Check(".env.example presente (sin valores reales)", (root / ".env.example").exists(),
                        "Plantilla de variables para el equipo"))
    env_example = root / ".env.example"
    if env_example.exists():
        values = [ln.split("=", 1)[1].strip() for ln in env_example.read_text().splitlines()
                  if "=" in ln and not ln.strip().startswith("#")]
        risky = [v for v in values if v and v.lower() not in ("", "false", "true", "22", "23", "cisco",
                                                               "changeme", "netadmin")]
        checks.append(Check(".env.example no contiene secretos", not risky,
                            "Valores vacíos o genéricos" if not risky else f"Revisar: {risky[:3]}"))
    tracked_env = False
    try:
        res = subprocess.run(["git", "ls-files", ".env"], cwd=root, capture_output=True, text=True, timeout=5)
        tracked_env = bool(res.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    checks.append(Check(".env no está versionado en git", not tracked_env,
                        "git ls-files .env vacío" if not tracked_env else "¡.env está en el repositorio!"))
    hits = scan_hardcoded_secrets(root)
    checks.append(Check("Sin secretos hardcodeados en el código", not hits,
                        "0 coincidencias" if not hits else ", ".join(hits[:5])))
    for doc in ("docs/politicas-ia.md", "docs/seguridad.md"):
        checks.append(Check(f"Documento {doc} presente", (root / doc).exists(), doc))
    return checks


# --------------------------------------------------------------------------- #
# Ejecución de pruebas
# --------------------------------------------------------------------------- #


def run_pytest(root: Path = ROOT, timeout: int = 600) -> tuple[list[TestCase], float]:
    xml_path = root / ".pytest_cache" / "junit.xml"
    xml_path.parent.mkdir(exist_ok=True)
    started = datetime.now()
    subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                    f"--junitxml={xml_path}", "tests"],
                   cwd=root, capture_output=True, text=True, timeout=timeout)
    duration = (datetime.now() - started).total_seconds()
    cases: list[TestCase] = []
    if not xml_path.exists():
        return cases, duration
    for tc in ET.parse(xml_path).getroot().iter("testcase"):
        classname = tc.get("classname", "")
        module = classname.split(".")[1] if "." in classname else classname
        failure = tc.find("failure") if tc.find("failure") is not None else tc.find("error")
        skipped = tc.find("skipped") is not None
        if skipped:
            continue
        cases.append(TestCase(module, tc.get("name", ""), failure is None,
                              (failure.get("message", "") if failure is not None else "")[:200]))
    return cases, duration


def build_report(root: Path = ROOT) -> QualityReport:
    tests, duration = run_pytest(root)
    return QualityReport(tests=tests, checks=security_checks(root), duration_s=duration)


def render_markdown(r: QualityReport) -> str:
    level = ("ALTA" if r.confidence >= 90 else "MEDIA" if r.confidence >= 75 else "BAJA")
    L = [
        "# Reporte de pruebas y porcentaje de confianza",
        "",
        f"> Generado automáticamente por `core/quality.py` el {r.generated_at}. "
        "No editar a mano: vuelva a ejecutar `python scripts/generate_test_report.py`.",
        "",
        f"## Resultado: **{r.confidence} %** de confianza (nivel {level})",
        "",
        "| Componente | Peso | Puntaje | Aporte |",
        "|---|---:|---:|---:|",
        f"| Pruebas automatizadas superadas | 60 % | {100 * r.pass_rate:.1f} % | {60 * r.pass_rate:.1f} |",
        f"| Controles de seguridad cumplidos | 25 % | {100 * r.security_score:.1f} % | {25 * r.security_score:.1f} |",
        f"| Cobertura de categorías | 15 % | {100 * r.coverage_score:.1f} % | {15 * r.coverage_score:.1f} |",
        "",
        "**Fórmula:** `Confianza = 0.60·(pruebas OK / total) + 0.25·(controles OK / total) "
        "+ 0.15·(categorías con pruebas OK / categorías)`",
        "",
        f"Total de pruebas: **{len(r.tests)}** · Superadas: **{sum(t.ok for t in r.tests)}** · "
        f"Fallidas: **{sum(not t.ok for t in r.tests)}** · Duración: {r.duration_s:.1f} s",
        "",
        "## Resultados por módulo",
        "",
        "| Categoría | Módulo | OK / Total |",
        "|---|---|---:|",
    ]
    cats = r.by_category()
    for key, label in CATEGORIES.items():
        ok, total = cats.get(key, (0, 0))
        L.append(f"| `{key}` | {label} | {ok} / {total} |")
    L += ["", "## Controles de ciberdefensa", "", "| Control | Estado | Detalle |", "|---|:---:|---|"]
    for c in r.checks:
        L.append(f"| {c.name} | {'✅' if c.ok else '❌'} | {c.detail} |")
    failed = [t for t in r.tests if not t.ok]
    L += ["", "## Pruebas fallidas", ""]
    L += [f"- `{t.category}::{t.name}` — {t.message}" for t in failed] or ["Ninguna."]
    L += ["", "## Detalle de casos de prueba", "", "| Categoría | Caso | Estado |", "|---|---|:---:|"]
    L += [f"| {t.category} | `{t.name}` | {'✅' if t.ok else '❌'} |" for t in r.tests]
    L += ["", "## Metodología", "",
          "- **Unitarias:** matemática de subredes contrastada con cálculos manuales (red, broadcast, "
          "máscara, gateway) y con la regla de 2 IPs útiles en /30.",
          "- **Propiedades:** ninguna subred se solapa, todas caben en la red base, cada VLAN tiene un /64 único.",
          "- **Generadores:** cada fabricante produce un archivo por equipo, sin secretos reales y con las IP del plan.",
          "- **Seguridad:** inyección de comandos, XSS en salida de terminal, enmascarado de contraseñas.",
          "- **Interfaz:** cada módulo se ejecuta con `streamlit.testing.AppTest` sin excepciones.",
          ""]
    return "\n".join(L)


def write_report(r: QualityReport, root: Path = ROOT) -> Path:
    out = root / "docs" / "pruebas.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(render_markdown(r), encoding="utf-8")
    return out
