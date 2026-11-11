"""
netdevops/deploy.py
===================
Módulo 5 — Despliegue guiado de configuración a los equipos.

Principio: la herramienta NUNCA inventa comandos al desplegar. Toma la misma
configuración que el Módulo 4 generó desde el plan IP, la parte en bloques
(un bloque = un comando de primer nivel con sus subcomandos) y clasifica cada
bloque en una categoría:

    hostname · vlans · ip · ports · routing · dhcp · seguridad · servicios

El operador elige qué categorías aplicar. Se respetan dependencias
(p. ej. asignar IP en un switch exige que existan las VLAN) y se conserva el
orden original del archivo, que ya está pensado para aplicarse de arriba a abajo.

Flujo de ejecución (SSH, Telnet de laboratorio o simulación):
    1. Respaldo de la configuración actual (configs_out/backups/, ignorado por git)
    2. Entrar a modo configuración según fabricante
    3. Enviar bloque por bloque y analizar la respuesta; si el equipo devuelve
       un error se detiene (fail-fast) y no se guarda la configuración
    4. Guardar (write memory / save) y ejecutar comandos de verificación
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterator

from core.validators import ValidationError, redact_secrets
from generators import render_device
from generators.common import Ctx

CATEGORIES: dict[str, str] = {
    "hostname": "Nombre del equipo",
    "vlans": "VLAN y spanning-tree",
    "ip": "Direcciones IP (interfaces, SVI, gateway)",
    "ports": "Puertos de acceso / troncales (encender, asignar VLAN)",
    "routing": "Enrutamiento (OSPF, rutas estáticas)",
    "dhcp": "Servidor DHCP",
    "seguridad": "Hardening (usuarios, SSH, SNMPv3, banner)",
    "servicios": "NAT, ACL, QoS, VPN, políticas de firewall",
}
DEFAULT_CATEGORIES = ("hostname", "vlans", "ip", "ports")

# Una categoría arrastra a otras para que el equipo no quede en un estado roto.
DEPENDENCIES = {
    "ip": {"switch": ["vlans"]},
    "ports": {"switch": ["vlans"]},
    "dhcp": {"any": ["ip"]},
    "routing": {"any": ["ip"]},
    "servicios": {"any": ["ip"]},
}

SWITCH_ROLES = ("core", "access", "server")

# Secretos que se inyectan desde el .env SOLO en el momento de enviar.
SECRET_ENV = {
    "<<ADMIN_SECRET>>": "ADMIN_SECRET",
    "<<ENABLE_SECRET>>": "ENABLE_SECRET",
    "<<VPN_PSK>>": "VPN_PSK",
    "<<SNMPV3_AUTH>>": "SNMPV3_AUTH",
    "<<SNMPV3_PRIV>>": "SNMPV3_PRIV",
}

ERROR_PATTERNS = {
    "Cisco": [r"% ?Invalid input", r"% ?Incomplete command", r"% ?Ambiguous command", r"% ?Unknown command",
              r"% ?Bad mask", r"% ?.*overlaps with"],
    "Huawei": [r"Error:", r"Unrecognized command", r"Wrong parameter", r"Incomplete command"],
    "Fortinet": [r"Command fail", r"entry not found", r"parse error", r"Unknown action", r"value parse error"],
    "MikroTik": [r"bad command name", r"expected end of command", r"failure:", r"syntax error",
                 r"input does not match", r"no such item"],
}

WRAPPERS = {
    #            entrar a configuración        salir y guardar
    "Cisco": (["configure terminal"], ["end", "write memory"]),
    "Huawei": (["system-view"], ["return", "save"]),
    "Fortinet": ([], []),      # FortiOS aplica y guarda cada bloque config…end
    "MikroTik": ([], []),      # RouterOS aplica y persiste cada comando
}

BACKUP_CMD = {"Cisco": "show running-config", "Huawei": "display current-configuration",
              "Fortinet": "show", "MikroTik": "/export"}

VERIFY_CMDS = {
    "Cisco": {"router": ["show ip interface brief", "show ip route"],
              "switch": ["show ip interface brief", "show vlan brief", "show interfaces trunk"]},
    "Huawei": {"router": ["display ip interface brief", "display ip routing-table"],
               "switch": ["display ip interface brief", "display vlan", "display port vlan"]},
    "Fortinet": {"router": ["get system interface", "get router info routing-table all"],
                 "switch": ["get system interface", "show switch vlan"]},
    "MikroTik": {"router": ["/ip address print", "/ip route print"],
                 "switch": ["/ip address print", "/interface bridge vlan print"]},
}

ROOT = Path(__file__).resolve().parent.parent
BACKUP_DIR = ROOT / "configs_out" / "backups"


# --------------------------------------------------------------------------- #
# Modelos
# --------------------------------------------------------------------------- #


@dataclass
class Block:
    category: str
    lines: list[str]

    @property
    def header(self) -> str:
        return self.lines[0] if self.lines else ""


@dataclass
class DeployPlan:
    vendor: str
    device_id: str
    hostname: str
    role: str
    categories: list[str]
    blocks: list[Block]
    pre: list[str]
    post: list[str]
    notes: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    @property
    def body_lines(self) -> list[str]:
        return [ln for b in self.blocks for ln in b.lines]

    def preview(self) -> str:
        """Texto para mostrar: los secretos quedan como marcadores (nunca se muestran)."""
        out, current = list(self.pre), None
        mark = "!" if self.vendor == "Cisco" else "#"
        for b in self.blocks:
            if b.category != current:
                out.append(f"{mark} ===== {CATEGORIES[b.category]} =====")
                current = b.category
            out.extend(b.lines)
        out.extend(self.post)
        return "\n".join(out)

    def count_by_category(self) -> dict[str, int]:
        c: dict[str, int] = {}
        for b in self.blocks:
            c[b.category] = c.get(b.category, 0) + len(b.lines)
        return c


@dataclass
class StepResult:
    phase: str          # backup | config | save | verify | info
    sent: str
    output: str
    ok: bool = True


# --------------------------------------------------------------------------- #
# Partición en bloques por fabricante
# --------------------------------------------------------------------------- #

_SKIP_CISCO = {"end", "write memory", "!"}
_SKIP_HUAWEI = {"system-view", "return", "save", "#"}


def _is_comment(vendor: str, line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    if vendor == "Cisco":
        return s.startswith("!")
    return s.startswith("#")


def split_blocks(vendor: str, text: str) -> list[list[str]]:
    """Divide la configuración en bloques de primer nivel (sin comentarios ni wrappers)."""
    lines = [ln.rstrip() for ln in text.splitlines()]
    blocks: list[list[str]] = []

    if vendor == "Fortinet":
        cur: list[str] | None = None
        for ln in lines:
            if _is_comment(vendor, ln) and cur is None:
                continue
            if cur is None and ln.startswith("config "):
                cur = [ln]
            elif cur is not None:
                cur.append(ln)
                if ln == "end":
                    blocks.append(cur)
                    cur = None
        return blocks

    if vendor == "MikroTik":
        for ln in lines:
            if _is_comment(vendor, ln):
                continue
            if ln.startswith("/"):
                blocks.append([ln])
            elif blocks:  # líneas "add ..." pertenecen al menú anterior (/ip firewall filter)
                blocks[-1].append(ln)
        return blocks

    # Cisco y Huawei: indentación (subcomandos empiezan con espacio)
    skip = _SKIP_CISCO if vendor == "Cisco" else _SKIP_HUAWEI
    in_banner = False
    for ln in lines:
        s = ln.strip()
        if in_banner:
            blocks[-1].append(ln)
            if s == "^C":
                in_banner = False
            continue
        if not s or s in skip or (vendor == "Cisco" and s.startswith("!")) or (vendor == "Huawei" and s.startswith("#")):
            continue
        if ln.startswith(" ") and blocks:
            blocks[-1].append(ln)
        else:
            blocks.append([ln])
            if s.startswith("banner "):
                in_banner = True
    return blocks


# --------------------------------------------------------------------------- #
# Clasificación
# --------------------------------------------------------------------------- #


def _classify_cisco(b: list[str]) -> str:
    h, body = b[0].strip(), "\n".join(b)
    if h.startswith("hostname"):
        return "hostname"
    if re.match(r"vlan \d+", h) or h.startswith(("spanning-tree", "vtp ")):
        return "vlans"
    if h.startswith("interface Tunnel") or "CE-PE" in body:
        return "servicios"
    if h.startswith("interface"):
        if " ip address" in body or h.startswith("interface Vlan"):
            return "ip"
        return "ports"
    if h in ("ip routing", "ipv6 unicast-routing") or h.startswith("ip default-gateway"):
        return "ip"
    if h.startswith(("router ospf", "ipv6 router ospf", "ip route 0.0.0.0", "ipv6 route ")):
        return "routing"
    if h.startswith(("router bgp", "ip route ")):
        return "servicios"  # rutas a la VPN / MPLS
    if h.startswith(("ip dhcp excluded-address", "ip dhcp pool")):
        return "dhcp"
    if h.startswith(("crypto ikev2", "crypto ipsec", "class-map", "policy-map", "ip nat",
                     "ip access-list extended")) or "ACL-NAT" in h:
        return "servicios"
    return "seguridad"


def _classify_huawei(b: list[str]) -> str:
    h, body = b[0].strip(), "\n".join(b)
    if h.startswith("sysname"):
        return "hostname"
    if h.startswith(("vlan ", "stp ", "voice-vlan")):
        return "vlans"
    if h.startswith("interface Tunnel") or "CE-PE" in body:
        return "servicios"
    if h.startswith(("interface", "port-group")):
        return "ip" if " ip address" in body else "ports"
    if h == "ipv6":
        return "ip"
    if h.startswith(("ospf", "ospfv3", "ip route-static 0.0.0.0", "ipv6 route-static")):
        return "routing"
    if h.startswith(("bgp", "ip route-static")):
        return "servicios"
    if h.startswith(("ip pool", "dhcp enable")):
        return "dhcp"
    if h.startswith(("ipsec", "ike ", "traffic ")) or re.match(r"acl number (2000|3000)", h):
        return "servicios"
    return "seguridad"


def _classify_fortinet(b: list[str]) -> str:
    h, body = b[0].strip(), "\n".join(b)
    if h in ("config switch vlan", "config switch stp settings", "config switch stp instance"):
        return "vlans"
    if h == "config system interface":
        return "servicios" if ("VPN-REMOTO" in body or "CE-PE" in body) else "ip"
    if h in ("config switch interface", "config switch physical-port"):
        return "ports"
    if h == "config router static":
        return "servicios" if "LAN-REMOTA" in body else "routing"
    if h in ("config router static6", "config router ospf", "config router ospf6"):
        return "routing"
    if h == "config system dhcp server":
        return "dhcp"
    if h.startswith(("config system global", "config system admin", "config system ntp", "config system snmp")):
        return "seguridad"
    return "servicios"


def _classify_mikrotik(b: list[str]) -> str:
    h = b[0].strip()
    if h.startswith("/system identity"):
        return "hostname"
    if h.startswith(("/interface bridge add", "/interface bridge vlan", "/interface vlan", "/interface bridge set")):
        return "vlans"
    if h.startswith(("/ip address", "/ipv6 address", "/interface list")):
        return "ip"
    if h.startswith(("/interface ethernet set", "/interface bridge port")):
        return "ports"
    if h.startswith(("/routing bgp",)):
        return "servicios"
    if h.startswith(("/routing", "/ip route", "/ipv6 route", "/interface ethernet switch")):
        return "routing"
    if h.startswith("/ip pool") and "SSTP" in h:
        return "servicios"
    if h.startswith(("/ip pool", "/ip dhcp-server")):
        return "dhcp"
    if h.startswith(("/ip firewall", "/queue", "/ip ipsec", "/ppp", "/interface sstp")):
        return "servicios"
    return "seguridad"


CLASSIFIERS = {"Cisco": _classify_cisco, "Huawei": _classify_huawei,
               "Fortinet": _classify_fortinet, "MikroTik": _classify_mikrotik}

# Subcomandos que dependen de otras categorías: se quitan si esa categoría no se aplica.
_SUBLINE_DEPS = {
    "servicios": re.compile(r"^\s+(ip nat|ip access-group|service-policy|nat outbound|traffic-filter|"
                            r"traffic-policy|qos lr|ip tcp adjust-mss)\b"),
    "routing": re.compile(r"^\s+(ip ospf|ipv6 ospf|ospfv3|ospf network-type)\b"),
    "dhcp": re.compile(r"^\s+dhcp select global\b"),
    "seguridad": re.compile(r"^\s+(ip dhcp snooping|dhcp snooping trusted|access-class)\b"),
}


def classify(vendor: str, blocks: list[list[str]]) -> list[Block]:
    fn = CLASSIFIERS[vendor]
    return [Block(fn(b), b) for b in blocks]


def resolve_categories(selected: list[str], role: str) -> tuple[list[str], list[str]]:
    """Agrega dependencias. Devuelve (categorías finales, notas)."""
    final, notes = list(dict.fromkeys(selected)), []
    kind = "switch" if role in SWITCH_ROLES else "router"
    changed = True
    while changed:
        changed = False
        for cat in list(final):
            for scope, deps in DEPENDENCIES.get(cat, {}).items():
                if scope in ("any", kind):
                    for d in deps:
                        if d not in final:
                            final.append(d)
                            notes.append(f"Se agregó «{CATEGORIES[d]}» porque «{CATEGORIES[cat]}» lo requiere.")
                            changed = True
    order = list(CATEGORIES)
    return sorted(final, key=order.index), notes


# --------------------------------------------------------------------------- #
# Constructor del plan de despliegue
# --------------------------------------------------------------------------- #


def _secrets_from_env() -> dict[str, str]:
    return {ph: os.getenv(env, "") for ph, env in SECRET_ENV.items() if os.getenv(env, "")}


def build_deploy_plan(ctx: Ctx, vendor: str, device_id: str, categories: list[str],
                      save: bool = True) -> DeployPlan:
    if not categories:
        raise ValidationError("Seleccione al menos una categoría para desplegar.")
    unknown = [c for c in categories if c not in CATEGORIES]
    if unknown:
        raise ValidationError(f"Categoría desconocida: {unknown}")

    gen = render_device(ctx, vendor, device_id)
    dev = ctx.topo.get(device_id)
    cats, notes = resolve_categories(categories, dev.role)
    secrets = _secrets_from_env()

    if "seguridad" in cats:
        needed = ["<<ADMIN_SECRET>>"] + (["<<ENABLE_SECRET>>"] if vendor == "Cisco" else [])
        missing = [SECRET_ENV[p] for p in needed if p not in secrets]
        if missing:
            raise ValidationError(
                "Hardening bloqueado: defina " + ", ".join(missing) + " en el .env. Aplicarlo sin "
                "usuario local podría dejarlo sin acceso al equipo.")

    blocks = classify(vendor, split_blocks(vendor, gen.text))
    selected: list[Block] = []
    skipped: list[str] = []
    for b in blocks:
        if b.category not in cats:
            continue
        lines = [b.lines[0]] + [ln for ln in b.lines[1:]
                                if not any(cat not in cats and rx.search(ln)
                                           for cat, rx in _SUBLINE_DEPS.items())]
        # Bloques con marcadores sin valor (IP del peer, LAN remota, secreto ausente) se omiten completos.
        pending = {m for ln in lines for m in re.findall(r"<<[A-Z0-9_]+>>", ln)} - set(secrets)
        if pending:
            skipped.append(f"{lines[0].strip()}  (falta {', '.join(sorted(pending))})")
            continue
        selected.append(Block(b.category, lines))

    # Fortinet: el bloque global trae otros ajustes; el nombre se aplica con un bloque mínimo.
    if vendor == "Fortinet" and "hostname" in cats:
        selected.insert(0, Block("hostname", ["config system global", f'    set hostname "{dev.hostname}"', "end"]))

    pre, post = WRAPPERS[vendor]
    post = list(post) if save else [x for x in post if x not in ("write memory", "save")]
    if not selected:
        raise ValidationError("No hay comandos para las categorías elegidas en este equipo.")
    return DeployPlan(vendor, device_id, dev.hostname, dev.role, cats, selected, list(pre), post,
                      notes, skipped)


def substitute_secrets(line: str, secrets: dict[str, str]) -> str:
    for ph, value in secrets.items():
        line = line.replace(ph, value)
    return line


def verify_commands(vendor: str, role: str) -> list[str]:
    return VERIFY_CMDS[vendor]["switch" if role in SWITCH_ROLES else "router"]


def detect_error(vendor: str, output: str) -> str | None:
    for pattern in ERROR_PATTERNS[vendor]:
        m = re.search(pattern + r".*", output)
        if m:
            return m.group(0).strip()[:160]
    return None


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def save_backup(hostname: str, vendor: str, text: str) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    path = BACKUP_DIR / f"{datetime.now():%Y%m%d_%H%M%S}_{vendor.lower()}_{hostname}.txt"
    path.write_text(text, encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# Ejecución
# --------------------------------------------------------------------------- #


class Transport:
    """Interfaz mínima que cumplen SSHSession, TelnetLabSession y el simulador."""

    def send_lines(self, lines: list[str]) -> str: ...      # noqa: E704
    def run(self, command: str): ...                          # noqa: E704


def execute(plan: DeployPlan, transport, *, backup: bool = True, verify: bool = True,
            stop_on_error: bool = True, secrets: dict[str, str] | None = None,
            on_step: Callable[[StepResult], None] | None = None) -> Iterator[StepResult]:
    """Ejecuta el plan sobre un transporte ya conectado y va emitiendo cada paso."""
    secrets = _secrets_from_env() if secrets is None else secrets
    known = list(secrets.values())

    def emit(step: StepResult) -> StepResult:
        step.output = redact_secrets(step.output, known)
        if on_step:
            on_step(step)
        return step

    if backup:
        res = transport.run(BACKUP_CMD[plan.vendor])
        path = save_backup(plan.hostname, plan.vendor, res.output)
        yield emit(StepResult("backup", BACKUP_CMD[plan.vendor],
                              f"Respaldo guardado en {_display_path(path)} ({len(res.output.splitlines())} líneas)"))

    if plan.pre:
        out = transport.send_lines(plan.pre)
        yield emit(StepResult("config", "\n".join(plan.pre), out))

    failed = False
    for block in plan.blocks:
        real = [substitute_secrets(ln, secrets) for ln in block.lines]
        out = transport.send_lines(real)
        err = detect_error(plan.vendor, out)
        yield emit(StepResult("config", "\n".join(block.lines), out if not err else f"% Error del equipo: {err}\n{out}",
                              ok=err is None))
        if not err and hasattr(transport, "on_block_applied"):
            transport.on_block_applied(block.category)
        if err and stop_on_error:
            failed = True
            break

    if failed:
        # Salir de modo configuración SIN guardar: el equipo conserva la config de arranque.
        exit_cmds = [c for c in plan.post if c not in ("write memory", "save")]
        if exit_cmds:
            transport.send_lines(exit_cmds)
        yield emit(StepResult("info", "", "Despliegue detenido por error. No se guardó la configuración; "
                                          "el respaldo permite revertir los cambios aplicados.", ok=False))
        return

    if plan.post:
        out = transport.send_lines(plan.post)
        yield emit(StepResult("save", "\n".join(plan.post), out, ok=detect_error(plan.vendor, out) is None))

    if verify:
        for cmd in verify_commands(plan.vendor, plan.role):
            res = transport.run(cmd)
            yield emit(StepResult("verify", cmd, res.output))
