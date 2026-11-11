"""
netdevops/telnet_client.py
==========================
Telnet mínimo SOLO para laboratorios locales (GNS3, EVE-NG, eNSP, CHR).

Telnet viaja en texto plano, así que la herramienta lo restringe:
* Solo destinos loopback o RFC 1918 (nunca Internet).
* Debe habilitarse explícitamente con ENABLE_TELNET_LAB=true en el .env.

Python 3.13 eliminó `telnetlib`; aquí se implementa la negociación IAC
básica (rechazar todas las opciones) sobre un socket TCP.
"""

from __future__ import annotations

import ipaddress
import socket
import time

from core.validators import ValidationError, redact_secrets, validate_command, validate_port

from .ssh_client import PROMPT_ANSWERS, CommandResult, TransportError, env_bool, validate_config_line

IAC, DONT, DO, WONT, WILL, SB, SE = 255, 254, 253, 252, 251, 250, 240


def ensure_lab_target(host: str) -> str:
    try:
        ip = ipaddress.ip_address(host.strip())
    except ValueError as exc:
        raise ValidationError("Telnet solo acepta IPs literales de laboratorio (no nombres DNS).") from exc
    if not (ip.is_private or ip.is_loopback):
        raise ValidationError("Telnet bloqueado: solo se permite hacia redes privadas o loopback.")
    if not env_bool("ENABLE_TELNET_LAB"):
        raise ValidationError("Telnet deshabilitado. Active ENABLE_TELNET_LAB=true en .env (solo laboratorio).")
    return str(ip)


def _strip_iac(sock: socket.socket, data: bytes) -> bytes:
    """Responde negativamente a toda negociación y devuelve solo el texto."""
    out, i = bytearray(), 0
    while i < len(data):
        b = data[i]
        if b == IAC and i + 1 < len(data):
            cmd = data[i + 1]
            if cmd in (DO, DONT, WILL, WONT) and i + 2 < len(data):
                opt = data[i + 2]
                reply = WONT if cmd in (DO, DONT) else DONT
                sock.sendall(bytes([IAC, reply, opt]))
                i += 3
                continue
            if cmd == SB:
                end = data.find(bytes([IAC, SE]), i)
                i = end + 2 if end != -1 else len(data)
                continue
            i += 2
            continue
        out.append(b)
        i += 1
    return bytes(out)


class TelnetLabSession:
    def __init__(self, host: str, username: str, password: str, port: int = 23, timeout: float = 6.0):
        self.host = ensure_lab_target(host)
        self.port = validate_port(port)
        self.username, self._password, self.timeout = username, password, timeout
        self.sock: socket.socket | None = None

    def __enter__(self):
        try:
            self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        except OSError as exc:
            raise TransportError(f"No se pudo abrir Telnet a {self.host}:{self.port}.") from exc
        self.sock.settimeout(0.3)
        banner = self._read(1.5)
        if "sername" in banner or "ogin" in banner:
            self._write(self.username)
            self._read(1.0)
        self._write(self._password)
        self._read(1.0)
        return self

    def __exit__(self, *exc):
        if self.sock:
            self.sock.close()

    def _write(self, line: str) -> None:
        self.sock.sendall(line.encode() + b"\r\n")

    def _read(self, quiet: float = 0.8, max_wait: float = 10.0) -> str:
        buf, start, last = bytearray(), time.monotonic(), time.monotonic()
        while time.monotonic() - start < max_wait:
            try:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                buf += _strip_iac(self.sock, chunk)
                last = time.monotonic()
            except socket.timeout:
                if time.monotonic() - last > quiet:
                    break
        return buf.decode("utf-8", errors="replace")

    def run(self, command: str) -> CommandResult:
        cmd = validate_command(command)
        t0 = time.monotonic()
        self._write(cmd)
        out = redact_secrets(self._read(), [self._password])
        return CommandResult(cmd, out, elapsed_ms=int((time.monotonic() - t0) * 1000))

    def send_lines(self, lines: list[str], quiet: float = 0.35) -> str:
        """Despliegue de configuración por Telnet (solo laboratorio)."""
        out = []
        for line in lines:
            validate_config_line(line)
            self._write(line)
            chunk = self._read(quiet)
            for rx, answer in PROMPT_ANSWERS:
                if rx.search(chunk[-120:]):
                    self._write(answer)
                    chunk += self._read(quiet)
                    break
            out.append(chunk)
        return redact_secrets("".join(out), [self._password])
