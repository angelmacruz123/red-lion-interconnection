"""
netdevops/serial_client.py
==========================
Módulo 5 — Conexión por CABLE DE CONSOLA (puerto serial / COM), como PuTTY "Serial".

Sirve para configurar un equipo recién sacado de la caja, que todavía no tiene
IP ni SSH. Usa pyserial y maneja los diálogos típicos de primer arranque:

* Cisco:  "Would you like to enter the initial configuration dialog? [yes/no]" → no
          "Press RETURN to get started"                                       → Enter
          "Would you like to terminate autoinstall? [yes]"                     → yes
          "Router>"                                                            → enable
* Huawei: "Press any key to get started" / cambio de contraseña inicial
* Login:  "Username:" / "Login:" / "Password:" con las credenciales indicadas

La consola es una conexión física local (no viaja por la red), por eso no
requiere verificación de host; las mismas validaciones de comandos aplican.
"""

from __future__ import annotations

import re
import time

from core.validators import ValidationError, redact_secrets, validate_command

from .ssh_client import MORE_RE, PAGING_OFF, PROMPT_ANSWERS, CommandResult, TransportError, validate_config_line

BAUD_RATES = (9600, 19200, 38400, 57600, 115200)

# COM1..COM256 (Windows), /dev/ttyUSB0 /dev/ttyS0 /dev/tty.usbserial-xxx (Linux/macOS)
# y socket://127.0.0.1:PUERTO (usado por las pruebas automáticas y por emuladores con consola TCP).
_PORT_RE = re.compile(r"^(COM\d{1,3}|/dev/(tty|cu)[A-Za-z0-9._\-]{1,40}|socket://127\.0\.0\.1:\d{2,5})$")

BOOT_DIALOGS = [
    (re.compile(r"initial configuration dialog\?\s*\[yes/no\]:?\s*$", re.I), "no"),
    (re.compile(r"terminate autoinstall\?\s*\[yes\]:?\s*$", re.I), "yes"),
    (re.compile(r"Press RETURN to get started", re.I), ""),
    (re.compile(r"Press any key to get started", re.I), ""),
]
_LOGIN_USER = re.compile(r"(Username|Login|login):\s*$")
_LOGIN_PASS = re.compile(r"Password:\s*$", re.I)
_PROMPT = re.compile(r"([\w.\-]+(\([\w\-]+\))?[>#]|<[\w.\-]+>|\[[\w.\-~]+\]|\[[^\]]+@[^\]]+\]\s*>)\s*$")


def list_serial_ports() -> list[tuple[str, str]]:
    """[(dispositivo, descripción)] de los puertos COM disponibles en este PC."""
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    return [(p.device, p.description or p.device) for p in sorted(list_ports.comports(), key=lambda p: p.device)]


def validate_serial_port(port: str) -> str:
    port = (port or "").strip()
    if not _PORT_RE.fullmatch(port):
        raise ValidationError(f"Puerto serial inválido: '{port}'. Ejemplos: COM1, COM3, /dev/ttyUSB0.")
    return port


class SerialConsoleSession:
    """Sesión interactiva por consola. Cumple la interfaz run() / send_lines() del despliegue."""

    def __init__(self, port: str, baudrate: int = 9600, username: str = "", password: str = "",
                 vendor: str = "Cisco", enable_secret: str = "", timeout: float = 1.0):
        self.port = validate_serial_port(port)
        if int(baudrate) not in BAUD_RATES:
            raise ValidationError(f"Velocidad no soportada: {baudrate}. Use {', '.join(map(str, BAUD_RATES))}.")
        self.baudrate = int(baudrate)
        self.username, self._password = username, password
        self.vendor, self._enable = vendor, enable_secret
        self.timeout = timeout
        self.ser = None
        self.warnings: list[str] = []
        self.last_output = ""

    # ------------------------------------------------------------------ #
    def __enter__(self) -> "SerialConsoleSession":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def connect(self) -> None:
        try:
            import serial
        except ImportError as exc:  # pragma: no cover
            raise TransportError("pyserial no está instalado (pip install pyserial).") from exc
        try:
            # 8N1 sin control de flujo: la configuración estándar de consola Cisco/Huawei/Fortinet/MikroTik
            self.ser = serial.serial_for_url(self.port, baudrate=self.baudrate, bytesize=8, parity="N",
                                             stopbits=1, timeout=0.1, write_timeout=2)
        except serial.SerialException as exc:
            msg = str(exc)
            if "PermissionError" in msg or "Access is denied" in msg or "Acceso denegado" in msg:
                raise TransportError(f"{self.port} está ocupado: cierre PuTTY u otro programa que lo use.") from exc
            if "FileNotFoundError" in msg or "could not open port" in msg:
                raise TransportError(f"No existe {self.port}. Revise el cable y el número de puerto en el "
                                     "Administrador de dispositivos → Puertos (COM y LPT).") from exc
            raise TransportError(f"No se pudo abrir {self.port}: {msg}") from exc
        self._wake_and_login()

    def close(self) -> None:
        if self.ser:
            try:
                self.ser.close()
            except Exception:  # noqa: BLE001
                pass
        self.ser = None

    # ------------------------------------------------------------------ #
    def _write(self, text: str) -> None:
        self.ser.write((text + "\r").encode())

    def _read_until_quiet(self, quiet: float = 0.6, max_wait: float = 25.0, answer_prompts: bool = False) -> str:
        buf, start, last = "", time.monotonic(), time.monotonic()
        while time.monotonic() - start < max_wait:
            chunk = self.ser.read(4096)
            if chunk:
                buf += chunk.decode("utf-8", errors="replace")
                last = time.monotonic()
                tail = buf[-160:]
                if MORE_RE.search(tail):
                    self.ser.write(b" ")
                elif answer_prompts:
                    for rx, answer in PROMPT_ANSWERS:
                        if rx.search(tail):
                            self._write(answer)
                            break
            elif time.monotonic() - last > quiet:
                break
        return buf

    def _wake_and_login(self) -> None:
        """Despierta la consola, supera diálogos de arranque, inicia sesión y entra a modo privilegiado."""
        out = ""
        for _ in range(12):  # máx. 12 interacciones
            self._write("")
            out = self._read_until_quiet(1.0)
            tail = out.rstrip()[-200:]
            handled = False
            for rx, answer in BOOT_DIALOGS:
                if rx.search(tail):
                    self._write(answer)
                    self._read_until_quiet(1.5)
                    handled = True
                    break
            if handled:
                continue
            if _LOGIN_USER.search(tail):
                if not self.username:
                    raise TransportError("El equipo pide usuario: complételo en el formulario o en .env.")
                self._write(self.username)
                out = self._read_until_quiet(1.0)
                tail = out.rstrip()[-200:]
            if _LOGIN_PASS.search(tail):
                if not self._password:
                    raise TransportError("El equipo pide contraseña de consola: complétela en el formulario o .env.")
                self.ser.write((self._password + "\r").encode())
                out = self._read_until_quiet(1.2)
                if re.search(r"(Login invalid|% Authentication failed|Error|incorrect)", out, re.I):
                    raise TransportError("Usuario o contraseña de consola incorrectos.")
                continue
            if _PROMPT.search(tail):
                self.last_output = out
                break
        else:
            raise TransportError(f"Sin respuesta reconocible en {self.port} a {self.baudrate} baudios. "
                                 "Verifique el cable de consola, la velocidad (normalmente 9600) y que el equipo "
                                 "haya terminado de arrancar.")
        self._ensure_privileged()
        paging = PAGING_OFF.get(self.vendor, "")
        if paging:
            self._write(paging)
            self._read_until_quiet(0.6)

    def _ensure_privileged(self) -> None:
        if self.vendor != "Cisco":
            return
        tail = self.last_output.rstrip()
        if tail.endswith("#"):
            if "(config" in tail[-40:]:  # se quedó en modo configuración de una sesión anterior
                self._write("end")
                self.last_output = self._read_until_quiet(0.6)
            return
        self._write("enable")
        out = self._read_until_quiet(0.8)
        if _LOGIN_PASS.search(out.rstrip()[-60:]):
            if not self._enable:
                raise TransportError("El equipo pide contraseña de enable: defínala en el formulario o en .env.")
            self.ser.write((self._enable + "\r").encode())
            out = self._read_until_quiet(0.8)
        if not out.rstrip().endswith("#"):
            raise TransportError("No se pudo entrar a modo privilegiado (enable).")
        self.last_output = out

    # ------------------------------------------------------------------ #
    def run(self, command: str) -> CommandResult:
        cmd = validate_command(command)
        t0 = time.monotonic()
        self._write(cmd)
        out = self._read_until_quiet()
        return CommandResult(cmd, redact_secrets(out, [self._password, self._enable]),
                             elapsed_ms=int((time.monotonic() - t0) * 1000))

    def send_lines(self, lines: list[str], quiet: float = 0.35) -> str:
        out = []
        for line in lines:
            validate_config_line(line)
            self._write(line)
            # "crypto key generate" y "write memory" tardan varios segundos por consola
            wait = 2.0 if re.match(r"\s*(crypto key generate|write memory|save)", line) else quiet
            out.append(self._read_until_quiet(wait, answer_prompts=True))
        return redact_secrets("".join(out), [self._password, self._enable])
