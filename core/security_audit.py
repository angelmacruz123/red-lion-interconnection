"""
core/security_audit.py
======================
Módulo 6 — Advertencia de configuraciones inseguras (ciberdefensa integrada).

Revisa un texto de configuración (generado por la herramienta, pegado por el
usuario o leído de un equipo) y advierte lo que contradice el mínimo
privilegio: servicios en claro (Telnet, HTTP), credenciales por defecto,
contraseñas sin cifrar, SNMP con comunidades conocidas, accesos sin ACL o
políticas "permitir todo".

Cada hallazgo trae severidad, línea, explicación y la corrección sugerida.
Se usa en: Módulo 4 (cada archivo generado se audita antes de descargarlo),
Módulo 5 (vista previa del despliegue) y Módulo 6 (laboratorio).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

SEVERITY_ORDER = {"alta": 0, "media": 1, "baja": 2}
DEFAULT_PASSWORDS = r"(cisco|admin|password|123456|12345678|huawei|admin@huawei|changeme|default|root|1234)"
DEFAULT_USERS = r"(admin|cisco|root|user|test)"


@dataclass(frozen=True)
class Finding:
    severity: str        # alta | media | baja
    rule: str
    line: int            # 1-based; 0 = toda la configuración
    text: str
    message: str
    fix: str


@dataclass(frozen=True)
class _Rule:
    rule: str
    severity: str
    pattern: re.Pattern
    message: str
    fix: str
    unless: re.Pattern | None = None   # si la línea también coincide con esto, no es hallazgo


def _rx(p: str) -> re.Pattern:
    return re.compile(p, re.IGNORECASE)


LINE_RULES: list[_Rule] = [
    # --- Servicios sin cifrar ------------------------------------------------
    _Rule("telnet", "alta", _rx(r"^\s*transport input (telnet|all|.*\btelnet\b)"),
          "Telnet habilitado en las líneas VTY: usuario y contraseña viajan en texto claro.",
          "Use «transport input ssh»."),
    _Rule("telnet", "alta", _rx(r"^\s*telnet server enable"),
          "Servidor Telnet habilitado (Huawei).", "Use «undo telnet server enable» y «stelnet server enable».",
          _rx(r"^\s*undo ")),
    _Rule("telnet", "alta", _rx(r"^\s*protocol inbound (telnet|all)"),
          "Las VTY aceptan Telnet (Huawei).", "Use «protocol inbound ssh»."),
    _Rule("telnet", "alta", _rx(r"set allowaccess .*\btelnet\b"),
          "Acceso administrativo por Telnet en una interfaz (FortiOS).", "Quite «telnet» de allowaccess."),
    _Rule("telnet", "alta", _rx(r"^/ip service (enable|set) .*telnet(?!.*disabled=yes)"),
          "Servicio Telnet activo (RouterOS).", "Use «/ip service disable telnet»."),
    _Rule("http", "media", _rx(r"^\s*ip http server\s*$"),
          "Servidor HTTP de gestión sin cifrar.", "Use «no ip http server» y, si hace falta, «ip http secure-server»."),
    _Rule("http", "media", _rx(r"set allowaccess .*\bhttp\b"),
          "Gestión web por HTTP en una interfaz (FortiOS).", "Use https en lugar de http."),
    _Rule("http", "media", _rx(r"^/ip service (enable|set) .*\bwww\b(?!-)(?!.*disabled=yes)"),
          "WebFig por HTTP activo (RouterOS).", "Use «/ip service disable www»; prefiera www-ssl."),
    _Rule("ssh-v1", "alta", _rx(r"^\s*ip ssh version 1\b"),
          "SSH versión 1 tiene vulnerabilidades conocidas.", "Use «ip ssh version 2»."),
    # --- Credenciales ----------------------------------------------------------
    _Rule("cred-default", "alta",
          _rx(rf"^\s*username {DEFAULT_USERS}\b.*\b(password|secret)\s+(\d\s+)?{DEFAULT_PASSWORDS}\s*$"),
          "Usuario y contraseña por defecto o triviales.", "Cree un usuario propio con una contraseña fuerte del gestor de secretos."),
    _Rule("cred-default", "alta",
          _rx(rf"^\s*(enable )?(password|secret)\s+(\d\s+)?{DEFAULT_PASSWORDS}\s*$"),
          "Contraseña por defecto o trivial.", "Use una contraseña fuerte (mínimo 12 caracteres) desde el .env."),
    _Rule("cred-default", "alta", _rx(rf"local-user {DEFAULT_USERS} password .*\b{DEFAULT_PASSWORDS}\s*$"),
          "Usuario local con contraseña por defecto (Huawei).", "Cambie la contraseña y use irreversible-cipher."),
    _Rule("cred-default", "alta", _rx(rf"/user add .*password=\"?{DEFAULT_PASSWORDS}\"?(\s|$)"),
          "Usuario con contraseña trivial (RouterOS).", "Use una contraseña fuerte y deshabilite el usuario admin."),
    _Rule("cleartext", "alta", _rx(r"^\s*enable password\b"),
          "«enable password» se guarda débilmente cifrado.", "Use «enable algorithm-type scrypt secret …»."),
    _Rule("cleartext", "media", _rx(r"^\s*username \S+ (privilege \d+ )?password (0 )?\S+"),
          "Contraseña de usuario guardada en texto claro o cifrado reversible.",
          "Use «username … algorithm-type scrypt secret …»."),
    _Rule("cleartext", "media", _rx(r"password simple\b"),
          "Contraseña en texto plano (Huawei «simple»).", "Use «irreversible-cipher»."),
    # --- SNMP ------------------------------------------------------------------
    _Rule("snmp", "alta", _rx(r"snmp-server community (public|private)\b"),
          "Comunidad SNMP por defecto: cualquiera puede leer (o cambiar) el equipo.",
          "Use SNMPv3 con autenticación y cifrado (authPriv)."),
    _Rule("snmp", "alta", _rx(r"snmp-agent community (read|write) (cipher )?(public|private)\b"),
          "Comunidad SNMP por defecto (Huawei).", "Use SNMPv3 (snmp-agent usm-user … privacy-mode aes128)."),
    _Rule("snmp", "alta", _rx(r"/snmp community .*name=(public|private)\b(?!.*disabled=yes)"),
          "Comunidad SNMP por defecto (RouterOS).", "Deshabilite «public» y use security=private (SNMPv3)."),
    _Rule("snmp", "media", _rx(r"^\s*snmp-server community \S+ RW\b"),
          "Comunidad SNMP con escritura: permite cambiar la configuración por SNMP.", "Use solo lectura o SNMPv3."),
    # --- Mínimo privilegio -----------------------------------------------------
    _Rule("permit-any", "media", _rx(r"^\s*(\d+\s+)?permit ip any any\b"),
          "ACL que permite todo el tráfico IP.", "Permita solo redes y puertos necesarios; termine con deny y log."),
    _Rule("permit-any", "media", _rx(r"^\s*access-list \d+ permit any\b"),
          "ACL estándar que permite cualquier origen.", "Restrinja al rango de gestión."),
    # (la administración desde la WAN y las políticas «todo a todo» se evalúan por bloque, abajo)
]


def _block_findings(lines: list[str]) -> list[Finding]:
    """Reglas que necesitan ver un bloque completo, no una sola línea."""
    out: list[Finding] = []
    text = "\n".join(lines)

    # Cisco: VTY sin ACL de origen
    for i, ln in enumerate(lines):
        if re.match(r"^\s*line vty\b", ln, re.I):
            block = []
            for nxt in lines[i + 1:]:
                if not nxt.startswith(" "):
                    break
                block.append(nxt)
            if not any("access-class" in b for b in block):
                out.append(Finding("media", "vty-acl", i + 1, ln.strip(),
                                   "Las líneas VTY no restringen desde qué red se administra el equipo.",
                                   "Agregue «access-class ACL-MGMT in» con la red de gestión."))
            if not any(re.search(r"exec-timeout", b) for b in block):
                out.append(Finding("baja", "timeout", i + 1, ln.strip(),
                                   "Las sesiones VTY no tienen tiempo de inactividad.", "Agregue «exec-timeout 10 0»."))

    # FortiOS: política que permite todo a todo, todos los servicios
    for m in re.finditer(r"(?ms)^\s*edit \d+\n(.*?)^\s*next", text):
        body = m.group(1)
        if ('set srcaddr "all"' in body and 'set dstaddr "all"' in body and 'set service "ALL"' in body
                and "set action accept" in body):
            line_no = text[:m.start()].count("\n") + 1
            out.append(Finding("media", "permit-any", line_no, m.group(0).strip().splitlines()[0],
                               "Política de firewall «todo a todo, todos los servicios».",
                               "Defina origen, destino y servicios concretos."))

    # FortiOS: administración desde la interfaz WAN
    for m in re.finditer(r'(?ms)^\s*edit "(wan\d?)"\n(.*?)^\s*next', text):
        if re.search(r"set allowaccess .*\b(https?|ssh|telnet)\b", m.group(2)):
            line_no = text[:m.start()].count("\n") + 1
            out.append(Finding("alta", "mgmt-wan", line_no, f'edit "{m.group(1)}"',
                               "La interfaz WAN permite administración desde Internet.",
                               "Deje solo «ping» en la WAN; administre por la red de gestión o VPN."))

    # RouterOS: usuario admin sigue activo
    if re.search(r"^/user\b", text, re.M | re.I) and not re.search(r"/user (set|disable) admin.*disabled=yes|/user disable admin", text, re.I):
        if re.search(r"/user add", text, re.I):
            out.append(Finding("media", "cred-default", 0, "/user",
                               "No se deshabilita el usuario «admin» que trae el equipo de fábrica.",
                               "Agregue «/user set admin disabled=yes»."))

    # Cisco: hay contraseñas y no se cifra lo que quede reversible
    if re.search(r"^\s*(username|line|enable)\b", text, re.M) and re.search(r"\bpassword\b", text) \
            and not re.search(r"^\s*service password-encryption", text, re.M):
        out.append(Finding("baja", "cleartext", 0, "service password-encryption",
                           "Sin «service password-encryption», las contraseñas tipo 7 quedan legibles.",
                           "Agregue «service password-encryption»."))
    return out


def audit(text: str) -> list[Finding]:
    lines = (text or "").splitlines()
    findings: list[Finding] = []
    for i, ln in enumerate(lines, start=1):
        if ln.strip().startswith(("!", "#")):
            continue
        for r in LINE_RULES:
            if r.pattern.search(ln) and not (r.unless and r.unless.search(ln)):
                findings.append(Finding(r.severity, r.rule, i, ln.strip(), r.message, r.fix))
    findings += _block_findings(lines)
    return sorted(findings, key=lambda f: (SEVERITY_ORDER[f.severity], f.line))


def summary(findings: list[Finding]) -> dict[str, int]:
    out = {"alta": 0, "media": 0, "baja": 0}
    for f in findings:
        out[f.severity] += 1
    return out


INSECURE_SAMPLE = """hostname R1
enable password cisco
username admin privilege 15 password 0 cisco
ip http server
snmp-server community public RO
access-list 10 permit any
line vty 0 4
 password cisco
 login
 transport input telnet
"""
