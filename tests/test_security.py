"""M6 · Anti-fuga de credenciales y controles del repositorio."""

from pathlib import Path

from core import quality
from core.validators import redact_secrets
from netdevops.ssh_client import ConnectionParams

ROOT = Path(__file__).resolve().parent.parent


def test_gitignore_excluye_env_y_salidas():
    lines = {l.strip() for l in (ROOT / ".gitignore").read_text().splitlines()}
    assert ".env" in lines and "configs_out/" in lines and "!.env.example" in lines


def test_env_example_sin_valores_secretos():
    for line in (ROOT / ".env.example").read_text().splitlines():
        if line.startswith(("NET_PASSWORD", "ADMIN_SECRET", "VPN_PSK", "ENABLE_SECRET", "SNMPV3")):
            assert line.split("=", 1)[1].strip() == ""


def test_no_hay_secretos_hardcodeados_en_el_codigo():
    assert quality.scan_hardcoded_secrets(ROOT) == []


def test_escaner_detecta_un_secreto_plantado(tmp_path):
    (tmp_path / "x.py").write_text('API_KEY = "abcd1234efgh"\n')
    assert quality.scan_hardcoded_secrets(tmp_path) == ["x.py:1"]


def test_redaccion_multi_fabricante():
    raw = ("username admin secret 9 $9$abc\nenable secret 5 $1$xyz\nsnmp-server community Pub123 RO\n"
           "set psksecret ENC hXk29\nset passwd Abc123!\n/user add name=a password=Sup3r\n"
           "pre-shared-key cipher MiClave")
    red = redact_secrets(raw)
    for leaked in ("$9$abc", "$1$xyz", "Pub123", "hXk29", "Abc123!", "Sup3r", "MiClave"):
        assert leaked not in red
    assert red.count("********") == 7


def test_redaccion_de_contrasena_conocida_en_salida():
    assert "Hunter22" not in redact_secrets("Login ok for Hunter22", ["Hunter22"])


def test_password_no_aparece_en_repr():
    p = ConnectionParams("10.0.0.1", "netadmin", "Hunter22")
    assert "Hunter22" not in repr(p)


def test_reporte_de_confianza_formula():
    r = quality.QualityReport(
        tests=[quality.TestCase(k, "t", True) for k in quality.CATEGORIES],
        checks=[quality.Check("a", True, ""), quality.Check("b", False, "")])
    assert r.pass_rate == 1.0 and r.security_score == 0.5 and r.coverage_score == 1.0
    assert r.confidence == 100.0  # confianza = pruebas superadas / total (rúbrica)
    r.tests.append(quality.TestCase("test_ipam", "test_x", False, "falló"))
    assert r.confidence == round(100 * len(quality.CATEGORIES) / (len(quality.CATEGORIES) + 1), 1)
    md = quality.render_markdown(r)
    assert f"Pruebas superadas: {r.passed} de {len(r.tests)}" in md and "| `test_ipam` |" in md
    assert "[P1]" in md and "FALLA" in md
