"""
core/validators.py
==================
Capa de ciberdefensa de entrada (Módulo 6).

Toda entrada del usuario pasa por aquí ANTES de llegar al motor IPAM, a las
plantillas CLI o a la consola SSH/Telnet. El objetivo es triple:

1. Evitar errores de sintaxis en las configuraciones generadas
   (un nombre con espacios o comillas rompe un `hostname` de Cisco/Huawei).
2. Evitar inyección de comandos en la consola NetDevOps
   (p. ej. `show ver ; reload`, saltos de línea ocultos, `$(...)`).
3. Evitar inyección HTML/JS al pintar salidas de equipos en la terminal web.

Cada función lanza `ValidationError` con un mensaje en español listo para UI.
"""

from __future__ import annotations

import html
import ipaddress
import re
from typing import Iterable

# --------------------------------------------------------------------------- #
# Excepción común
# --------------------------------------------------------------------------- #


class ValidationError(ValueError):
    """Error de validación con mensaje apto para mostrar al usuario."""


# --------------------------------------------------------------------------- #
# Expresiones regulares (lista blanca, nunca lista negra sola)
# --------------------------------------------------------------------------- #

# Nombre de proyecto: letras (incluye tildes/ñ), números, espacio, guion y guion bajo.
_PROJECT_RE = re.compile(r"^[A-Za-z0-9ÁÉÍÓÚÜÑáéíóúüñ _\-]{3,48}$")

# Hostname RFC 1123 (1–63 caracteres por etiqueta), válido en IOS/VRP/FortiOS/RouterOS.
_HOSTNAME_RE = re.compile(r"^(?=.{1,63}$)[A-Za-z0-9](?:[A-Za-z0-9\-]*[A-Za-z0-9])?$")

# FQDN o hostname (para destinos SSH).
_FQDN_RE = re.compile(
    r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?\.)*"
    r"[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?$"
)

# Usuario de equipo de red.
_USERNAME_RE = re.compile(r"^[A-Za-z0-9._\-]{1,32}$")

# Metacaracteres que NO deben aparecer en comandos enviados a un equipo.
# El pipe "|" SÍ se permite porque los CLI de red lo usan para filtros
# (`show run | include vlan`), pero no los operadores de shell encadenados.
_FORBIDDEN_CMD_TOKENS = (";", "&&", "||", "`", "$(", "${", ">", "<", "\\x", "\x00")

# Comandos destructivos que requieren confirmación explícita.
_DESTRUCTIVE_PATTERNS = (
    r"^\s*reload\b",
    r"^\s*reboot\b",
    r"^\s*erase\b",
    r"^\s*write\s+erase\b",
    r"^\s*format\b",
    r"^\s*delete\b",
    r"^\s*reset\s+saved-configuration\b",  # Huawei
    r"^\s*execute\s+(factoryreset|reboot|formatlogdisk)\b",  # FortiOS
    r"^\s*/system\s+(reset-configuration|reboot)\b",  # MikroTik
    r"^\s*system\s+(reset-configuration|reboot)\b",
)
_DESTRUCTIVE_RE = re.compile("|".join(_DESTRUCTIVE_PATTERNS), re.IGNORECASE)

MAX_COMMAND_LEN = 256
MAX_BATCH = 50

# --------------------------------------------------------------------------- #
# Validadores de parámetros de diseño (Módulo 1)
# --------------------------------------------------------------------------- #


def validate_project_name(name: str) -> str:
    name = (name or "").strip()
    if not _PROJECT_RE.fullmatch(name):
        raise ValidationError(
            "El nombre del proyecto debe tener 3–48 caracteres: letras, números, "
            "espacios, guion o guion bajo."
        )
    return name


def slugify_hostname(text: str, max_len: int = 20) -> str:
    """Convierte un texto libre en un prefijo de hostname seguro (A-Z0-9-)."""
    trans = str.maketrans("ÁÉÍÓÚÜÑáéíóúüñ", "AEIOUUNaeiouun")
    clean = re.sub(r"[^A-Za-z0-9]+", "-", (text or "").translate(trans)).strip("-")
    clean = clean.upper()[:max_len].strip("-")
    return clean or "NET"


def validate_hostname(name: str) -> str:
    name = (name or "").strip()
    if not _HOSTNAME_RE.fullmatch(name):
        raise ValidationError(f"Hostname inválido: '{name}'. Use A-Z, 0-9 y guion (máx. 63).")
    return name


def validate_int_range(value, minimum: int, maximum: int, field: str) -> int:
    try:
        ivalue = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field}: debe ser un número entero.") from exc
    if not minimum <= ivalue <= maximum:
        raise ValidationError(f"{field}: debe estar entre {minimum} y {maximum}.")
    return ivalue


def validate_ipv4_network(cidr: str, min_prefix: int = 8, max_prefix: int = 28) -> ipaddress.IPv4Network:
    """Red base IPv4. strict=True: rechaza '10.0.0.5/16' (host bits encendidos)."""
    try:
        net = ipaddress.IPv4Network((cidr or "").strip(), strict=True)
    except ValueError as exc:
        raise ValidationError(
            f"Red IPv4 inválida '{cidr}'. Ejemplo válido: 10.20.0.0/16 (sin bits de host)."
        ) from exc
    if not min_prefix <= net.prefixlen <= max_prefix:
        raise ValidationError(f"El prefijo IPv4 debe estar entre /{min_prefix} y /{max_prefix}.")
    if not (net.is_private or net.subnet_of(ipaddress.IPv4Network("100.64.0.0/10"))):
        raise ValidationError(
            "La red base LAN debe ser privada (RFC 1918) o CGNAT (100.64.0.0/10)."
        )
    return net


def validate_ipv6_network(cidr: str, min_prefix: int = 32, max_prefix: int = 56) -> ipaddress.IPv6Network:
    try:
        net = ipaddress.IPv6Network((cidr or "").strip(), strict=True)
    except ValueError as exc:
        raise ValidationError(
            f"Red IPv6 inválida '{cidr}'. Ejemplo válido: 2001:db8:acad::/48."
        ) from exc
    if not min_prefix <= net.prefixlen <= max_prefix:
        raise ValidationError(f"El prefijo IPv6 debe estar entre /{min_prefix} y /{max_prefix}.")
    return net


def validate_ipv4_host(ip: str) -> ipaddress.IPv4Address:
    try:
        return ipaddress.IPv4Address((ip or "").strip())
    except ValueError as exc:
        raise ValidationError(f"Dirección IPv4 inválida: '{ip}'.") from exc


def validate_target_host(host: str) -> str:
    """Destino SSH/Telnet: IPv4, IPv6 o FQDN. Nada de espacios ni rutas."""
    host = (host or "").strip()
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    if _FQDN_RE.fullmatch(host):
        return host
    raise ValidationError(f"Destino inválido: '{host}'. Use una IP o un nombre DNS.")


def validate_port(port) -> int:
    return validate_int_range(port, 1, 65535, "Puerto")


def validate_username(user: str) -> str:
    user = (user or "").strip()
    if not _USERNAME_RE.fullmatch(user):
        raise ValidationError("Usuario inválido (1–32 caracteres: letras, números, . _ -).")
    return user


# --------------------------------------------------------------------------- #
# Validación de comandos (Módulo 5)
# --------------------------------------------------------------------------- #


def is_destructive(command: str) -> bool:
    return bool(_DESTRUCTIVE_RE.search(command or ""))


def validate_command(command: str) -> str:
    """Valida UN comando de CLI de red. Lanza ValidationError si es peligroso."""
    if command is None:
        raise ValidationError("Comando vacío.")
    cmd = command.strip()
    if not cmd:
        raise ValidationError("Comando vacío.")
    if len(cmd) > MAX_COMMAND_LEN:
        raise ValidationError(f"Comando demasiado largo (máx. {MAX_COMMAND_LEN}).")
    if any(ch in cmd for ch in ("\n", "\r")):
        raise ValidationError("Un comando no puede contener saltos de línea ocultos.")
    if any(ord(ch) < 32 and ch != "\t" for ch in cmd):
        raise ValidationError("El comando contiene caracteres de control no permitidos.")
    for token in _FORBIDDEN_CMD_TOKENS:
        if token in cmd:
            raise ValidationError(f"Token no permitido en el comando: '{token}'.")
    return cmd


def parse_command_batch(text: str, allow_destructive: bool = False) -> list[str]:
    """Convierte el textarea del usuario en una lista de comandos validados.

    - Ignora líneas vacías y comentarios (`#` o `!` al inicio).
    - Rechaza el lote completo si una línea es inválida (fail-closed).
    """
    commands: list[str] = []
    for lineno, raw in enumerate((text or "").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith(("#", "!")):
            continue
        try:
            cmd = validate_command(line)
        except ValidationError as exc:
            raise ValidationError(f"Línea {lineno}: {exc}") from exc
        if is_destructive(cmd) and not allow_destructive:
            raise ValidationError(
                f"Línea {lineno}: '{cmd}' es destructivo. Active la confirmación explícita."
            )
        commands.append(cmd)
    if not commands:
        raise ValidationError("No hay comandos para ejecutar.")
    if len(commands) > MAX_BATCH:
        raise ValidationError(f"Máximo {MAX_BATCH} comandos por lote.")
    return commands


# --------------------------------------------------------------------------- #
# Salida segura y anti-fuga de credenciales
# --------------------------------------------------------------------------- #


def escape_output(text: str) -> str:
    """Escapa salida de equipos antes de inyectarla en HTML (anti-XSS)."""
    return html.escape(text or "", quote=True)


_SECRET_LINE_PATTERNS = [
    # Cisco / Huawei / genérico
    re.compile(r"(?i)(\b(?:password|secret|key-string|pre-shared-key|psk)\b\s+"
               r"(?:(?:\d|cipher|simple|irreversible-cipher|ENC)\s+)?)(\S+)"),
    # FortiOS: set passwd ENC xxx / set psksecret ENC xxx
    re.compile(r"(?i)(\bset\s+(?:passwd|password|psksecret)\s+(?:ENC\s+)?)(\S+)"),
    # MikroTik: password=xxx secret=xxx
    re.compile(r"(?i)(\b(?:password|secret)=)(\S+)"),
    # SNMP community
    re.compile(r"(?i)(\bsnmp-server\s+community\s+)(\S+)"),
]


def redact_secrets(text: str, extra_secrets: Iterable[str] = ()) -> str:
    """Enmascara contraseñas/PSK en salidas y logs antes de mostrarlas o guardarlas."""
    out = text or ""
    for pattern in _SECRET_LINE_PATTERNS:
        out = pattern.sub(lambda m: m.group(1) + "********", out)
    for secret in extra_secrets:
        if secret and len(secret) >= 3:
            out = out.replace(secret, "********")
    return out
