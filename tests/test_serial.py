"""M5 · Consola serial (cable de consola / COM), probada con un Cisco de fábrica emulado.

pyserial acepta URLs `socket://` con la misma API que un puerto COM real, así que la
prueba ejercita exactamente el mismo código que se usa con el cable de consola.
"""

import socket
import threading

import pytest

from core.validators import ValidationError
from netdevops import deploy
from netdevops.deploy import build_deploy_plan, execute
from netdevops.serial_client import SerialConsoleSession, list_serial_ports, validate_serial_port
from netdevops.ssh_client import TransportError
from generators.common import Ctx


def _factory_cisco(sock, log, login=None):
    """Emula la consola de un Cisco recién encendido (diálogo inicial → Router> → enable)."""
    conn, _ = sock.accept()
    host, mode, stage = "Router", "user", "dialog" if login is None else "login_user"

    def prompt():
        return {"user": f"{host}>", "priv": f"{host}#", "conf": f"{host}(config)#",
                "if": f"{host}(config-if)#"}[mode]

    buf = ""
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break
            buf += data.decode()
            while "\r" in buf:
                line, buf = buf.split("\r", 1)
                cmd = line.strip()
                log.append(cmd)
                if stage == "dialog":
                    if cmd == "":
                        conn.sendall(b"\r\n--- System Configuration Dialog ---\r\n"
                                     b"Would you like to enter the initial configuration dialog? [yes/no]: ")
                    elif cmd == "no":
                        stage = "return"
                        conn.sendall(b"\r\nPress RETURN to get started!\r\n")
                    continue
                if stage == "return":
                    stage = "cli"
                    conn.sendall(prompt().encode())
                    continue
                if stage == "login_user":
                    if cmd == "":
                        conn.sendall(b"\r\nUser Access Verification\r\n\r\nUsername: ")
                    else:
                        stage = "login_pass" if cmd == login[0] else "login_user"
                        conn.sendall(b"Password: " if cmd == login[0] else b"\r\nUsername: ")
                    continue
                if stage == "login_pass":
                    if cmd == login[1]:
                        stage = "cli"
                        conn.sendall(("\r\n" + prompt()).encode())
                    else:
                        stage = "login_user"
                        conn.sendall(b"\r\n% Authentication failed\r\n\r\nUsername: ")
                    continue
                out = ""
                if cmd == "enable":
                    mode = "priv"
                elif cmd == "configure terminal":
                    mode = "conf"
                elif cmd.startswith("hostname "):
                    host = cmd.split()[1]
                elif cmd.startswith("interface "):
                    mode = "if"
                elif cmd == "end":
                    mode = "priv"
                elif cmd == "write memory":
                    out = "Building configuration...\r\n[OK]\r\n"
                elif cmd.startswith("show"):
                    out = f"{cmd} output\r\n"
                conn.sendall(("\r\n" + out + prompt()).encode())
    except OSError:
        pass


@pytest.fixture
def console():
    def start(login=None):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        log: list[str] = []
        threading.Thread(target=_factory_cisco, args=(sock, log, login), daemon=True).start()
        return f"socket://127.0.0.1:{sock.getsockname()[1]}", log
    return start


@pytest.fixture(autouse=True)
def _respaldos_temporales(monkeypatch, tmp_path):
    for env in deploy.SECRET_ENV.values():
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setattr(deploy, "BACKUP_DIR", tmp_path)


def test_equipo_de_fabrica_supera_dialogo_y_entra_a_enable(console):
    url, log = console()
    with SerialConsoleSession(url, 9600) as s:
        r = s.run("show version")
    assert "no" in log and "enable" in log and "terminal length 0" in log
    assert "show version output" in r.output


def test_despliegue_por_consola_configura_nombre_e_ip(console, cfg, plan, topo):
    url, log = console()
    dp = build_deploy_plan(Ctx(cfg, plan, topo), "Cisco", "R-DIST", ["hostname", "ip"])
    with SerialConsoleSession(url, 9600) as s:
        steps = list(execute(dp, s, secrets={}))
    assert all(st.ok for st in steps)
    assert "configure terminal" in log and "write memory" in log
    assert f"hostname {topo.get('R-DIST').hostname}" in log
    assert any(l.startswith("ip address 172.31.255.2") for l in log)


def test_login_de_consola_con_usuario(console):
    url, log = console(login=("netadmin", "Cons0la!"))
    with SerialConsoleSession(url, 9600, "netadmin", "Cons0la!") as s:
        out = s.run("show clock").output
    assert "show clock output" in out and "Cons0la!" not in out


def test_login_de_consola_pide_usuario_si_falta(console):
    url, _ = console(login=("netadmin", "x"))
    with pytest.raises(TransportError, match="pide usuario"):
        SerialConsoleSession(url, 9600).connect()


def test_puerto_inexistente_mensaje_claro():
    with pytest.raises(TransportError):
        SerialConsoleSession("COM250", 9600).connect()


@pytest.mark.parametrize("port", ["COM1", "COM12", "/dev/ttyUSB0", "/dev/tty.usbserial-1410"])
def test_puertos_validos(port):
    assert validate_serial_port(port) == port


@pytest.mark.parametrize("port", ["COM1; del *", "http://x", "socket://8.8.8.8:23", "", "LPT1"])
def test_puertos_invalidos(port):
    with pytest.raises(ValidationError):
        validate_serial_port(port)


def test_velocidad_invalida():
    with pytest.raises(ValidationError):
        SerialConsoleSession("COM1", 1234)


def test_listado_de_puertos_no_falla():
    assert isinstance(list_serial_ports(), list)
