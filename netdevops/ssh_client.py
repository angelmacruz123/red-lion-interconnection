"""
netdevops/ssh_client.py
=======================
Módulo 5 — Transporte SSH real con paramiko.

Decisiones de seguridad:
* Política de host key = RejectPolicy por defecto (se verifica contra
  ~/.ssh/known_hosts). Solo si ALLOW_UNKNOWN_HOSTS=true en el .env se acepta
  la clave en modo laboratorio (AutoAddPolicy) y se avisa en la salida.
* Las credenciales llegan desde el .env o desde un campo password del
  formulario; nunca se escriben a disco ni a los logs (redact_secrets).
* Cada comando se valida con core.validators antes de enviarse.
* Se usa invoke_shell (no exec_command) porque la mayoría de los NOS
  (IOS, VRP, FortiOS, RouterOS) no soportan bien el canal exec.
"""

from __future__ import annotations

import os
import re
import socket
import time
from dataclasses import dataclass, field
from typing import Callable, Iterator

from core.validators import (ValidationError, redact_secrets, validate_command, validate_port,
                             validate_target_host, validate_username)

# Comando para desactivar el paginado ("--More--") según fabricante
PAGING_OFF = {
    "Cisco": "terminal length 0",
    "Huawei": "screen-length 0 temporary",
    "Fortinet": "",           # FortiOS: se configura con 'config system console' (no por sesión)
    "MikroTik": "",           # RouterOS no pagina con +ct en el usuario
}


# Respuestas seguras a prompts interactivos durante el despliegue
PROMPT_ANSWERS = [
    (re.compile(r"\[Y/N\]:?\s*$", re.I), "y"),          # Huawei: save / confirmaciones
    (re.compile(r"\[yes/no\]:?\s*$", re.I), "no"),      # Cisco: ¿reemplazar llaves RSA? → conservar
    (re.compile(r"\[confirm\]\s*$", re.I), ""),         # Cisco: confirmaciones
    (re.compile(r"Destination filename \[.*\]\?\s*$"), ""),
]
MORE_RE = re.compile(r"(--More--|---- More ----|--more--)\s*$")
MAX_CONFIG_LINE = 512


def validate_config_line(line: str) -> str:
    """Línea de configuración generada: sin saltos ocultos, control ni marcadores pendientes."""
    if any(ch in line for ch in ("\n", "\r", "\x00")) or any(ord(c) < 32 and c != "\t" for c in line):
        raise ValidationError("Línea de configuración con caracteres de control.")
    if len(line) > MAX_CONFIG_LINE:
        raise ValidationError("Línea de configuración demasiado larga.")
    if "<<" in line and ">>" in line:
        raise ValidationError(f"Marcador sin reemplazar: {line.strip()[:60]}")
    return line


class TransportError(RuntimeError):
    """Error de conexión con mensaje entendible para el operador."""


@dataclass
class CommandResult:
    command: str
    output: str
    ok: bool = True
    elapsed_ms: int = 0


@dataclass
class ConnectionParams:
    host: str
    username: str
    password: str = field(repr=False)  # repr=False: nunca se imprime por accidente
    port: int = 22
    vendor: str = "Cisco"
    timeout: float = 8.0

    def validated(self) -> "ConnectionParams":
        validate_target_host(self.host)
        validate_username(self.username)
        validate_port(self.port)
        if not self.password:
            raise ValidationError("Falta la contraseña (defínala en .env o en el formulario).")
        return self


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "si", "sí")


class SSHSession:
    """Sesión SSH interactiva con un equipo de red."""

    def __init__(self, params: ConnectionParams):
        self.params = params.validated()
        self._client = None
        self._chan = None
        self.warnings: list[str] = []

    # ---------------------------------------------------------------------
    def __enter__(self) -> "SSHSession":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def connect(self) -> None:
        try:
            import paramiko
        except ImportError as exc:  # pragma: no cover
            raise TransportError("paramiko no está instalado (pip install paramiko).") from exc

        client = paramiko.SSHClient()
        client.load_system_host_keys()
        known = os.path.expanduser("~/.ssh/known_hosts")
        if os.path.exists(known):
            client.load_host_keys(known)
        if env_bool("ALLOW_UNKNOWN_HOSTS"):
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.warnings.append("ALLOW_UNKNOWN_HOSTS=true: clave de host aceptada sin verificar (solo laboratorio).")
        else:
            client.set_missing_host_key_policy(paramiko.RejectPolicy())

        p = self.params
        try:
            client.connect(hostname=p.host, port=p.port, username=p.username, password=p.password,
                           timeout=p.timeout, banner_timeout=p.timeout, auth_timeout=p.timeout,
                           look_for_keys=False, allow_agent=False)
        except paramiko.AuthenticationException as exc:
            raise TransportError("Autenticación fallida: usuario o contraseña incorrectos.") from exc
        except paramiko.BadHostKeyException as exc:
            raise TransportError("¡La clave del host CAMBIÓ! Posible ataque MITM. Conexión abortada.") from exc
        except paramiko.SSHException as exc:
            msg = str(exc)
            if "not found in known_hosts" in msg or "Server" in msg and "not found" in msg:
                raise TransportError(
                    "Host desconocido: agregue su clave a ~/.ssh/known_hosts "
                    "(ssh-keyscan) o, solo en laboratorio, ALLOW_UNKNOWN_HOSTS=true en .env."
                ) from exc
            raise TransportError(f"Error SSH: {redact_secrets(msg, [p.password])}") from exc
        except (socket.timeout, TimeoutError) as exc:
            raise TransportError(f"Tiempo de espera agotado conectando a {p.host}:{p.port}.") from exc
        except (OSError, paramiko.ssh_exception.NoValidConnectionsError) as exc:
            raise TransportError(f"No se pudo conectar a {p.host}:{p.port} ({exc.__class__.__name__}).") from exc

        self._client = client
        self._chan = client.invoke_shell(width=250, height=1000)
        self._chan.settimeout(p.timeout)
        self.last_output = self._read_until_quiet(1.0)  # banner / MOTD + prompt
        paging = PAGING_OFF.get(p.vendor, "")
        if paging:
            self._send(paging)
            self._read_until_quiet(0.8)

    def close(self) -> None:
        if self._client:
            self._client.close()
        self._client = self._chan = None

    # ---------------------------------------------------------------------
    def _send(self, line: str) -> None:
        self._chan.send(line + "\n")

    def _read_until_quiet(self, quiet: float = 0.8, max_wait: float = 30.0,
                          answer_prompts: bool = False) -> str:
        """Lee hasta que el equipo deje de enviar datos `quiet` segundos.

        Avanza el paginado (--More--) y, en despliegue, responde prompts conocidos.
        """
        buf, start, last = [], time.monotonic(), time.monotonic()
        while time.monotonic() - start < max_wait:
            if self._chan.recv_ready():
                buf.append(self._chan.recv(65535).decode("utf-8", errors="replace"))
                last = time.monotonic()
                tail = "".join(buf)[-120:]
                if MORE_RE.search(tail):
                    self._chan.send(" ")
                elif answer_prompts:
                    for rx, answer in PROMPT_ANSWERS:
                        if rx.search(tail):
                            self._send(answer)
                            break
            elif time.monotonic() - last > quiet:
                break
            else:
                time.sleep(0.03)
        return "".join(buf)

    def ensure_privileged(self, enable_secret: str = "") -> None:
        """Cisco: si el prompt es 'R1>' entra a modo privilegiado (enable)."""
        if self.params.vendor != "Cisco" or not self.last_output.rstrip().endswith(">"):
            return
        self._send("enable")
        out = self._read_until_quiet(0.8)
        if "assword" in out:
            if not enable_secret:
                raise TransportError("El equipo pide contraseña de enable: defínala en el formulario o en .env.")
            self._chan.send(enable_secret + "\n")
            out = self._read_until_quiet(0.8)
        if not out.rstrip().endswith("#"):
            raise TransportError("No se pudo entrar a modo privilegiado (enable).")
        self.last_output = out

    def send_lines(self, lines: list[str], quiet: float = 0.35) -> str:
        """Envía líneas de configuración (despliegue) y devuelve la salida acumulada."""
        out = []
        for line in lines:
            validate_config_line(line)
            self._send(line)
            out.append(self._read_until_quiet(quiet, answer_prompts=True))
        text = "".join(out)
        return redact_secrets(text, [self.params.password])

    def run(self, command: str) -> CommandResult:
        cmd = validate_command(command)
        t0 = time.monotonic()
        self._send(cmd)
        out = self._read_until_quiet()
        return CommandResult(cmd, redact_secrets(out, [self.params.password]),
                             elapsed_ms=int((time.monotonic() - t0) * 1000))

    def run_batch(self, commands: list[str],
                  on_result: Callable[[CommandResult], None] | None = None) -> list[CommandResult]:
        results = []
        for cmd in commands:
            try:
                res = self.run(cmd)
            except (ValidationError, OSError, socket.timeout) as exc:
                res = CommandResult(cmd, f"% Error: {exc}", ok=False)
            results.append(res)
            if on_result:
                on_result(res)
        return results


def stream_batch(params: ConnectionParams, commands: list[str]) -> Iterator[CommandResult]:
    """Generador para la UI: abre sesión, emite cada resultado y cierra siempre."""
    with SSHSession(params) as session:
        for w in session.warnings:
            yield CommandResult("# aviso", w, ok=True)
        for cmd in commands:
            try:
                yield session.run(cmd)
            except (ValidationError, OSError, socket.timeout) as exc:
                yield CommandResult(cmd, f"% Error: {exc}", ok=False)
