"""M5 · Consola NetDevOps: SSH real contra un servidor paramiko local, Telnet de laboratorio y simulador."""

import socket
import threading

import paramiko
import pytest

from core.validators import ValidationError
from generators import render_device
from generators.common import Ctx
from netdevops.simulator import LabSimulator
from netdevops.ssh_client import ConnectionParams, SSHSession, TransportError, stream_batch
from netdevops.telnet_client import IAC, DO, TelnetLabSession, ensure_lab_target

USER, PWD = "netadmin", "LabPass123"


# --------------------------------------------------------------------------- #
# Servidor SSH falso (emula un IOS) para pruebas de integración sin hardware
# --------------------------------------------------------------------------- #
class _FakeIOS(paramiko.ServerInterface):
    def check_auth_password(self, username, password):
        return paramiko.AUTH_SUCCESSFUL if (username, password) == (USER, PWD) else paramiko.AUTH_FAILED

    def get_allowed_auths(self, username):
        return "password"

    def check_channel_request(self, kind, chanid):
        return paramiko.OPEN_SUCCEEDED

    def check_channel_pty_request(self, *a):
        return True

    def check_channel_shell_request(self, channel):
        return True


def _serve(sock, host_key):
    try:
        conn, _ = sock.accept()
        t = paramiko.Transport(conn)
        t.add_server_key(host_key)
        t.start_server(server=_FakeIOS())
        chan = t.accept(5)
        if chan is None:
            return
        chan.send("LAB-R1#")
        buf = ""
        while True:
            data = chan.recv(1024)
            if not data:
                break
            buf += data.decode()
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                line = line.strip()
                if line == "show clock":
                    chan.send("*10:00:00.000 COT Tue Nov 10 2026\r\nLAB-R1#")
                elif line == "show run | include secret":
                    chan.send(f"username netadmin secret 9 {PWD}\r\nLAB-R1#")
                else:
                    chan.send("\r\nLAB-R1#")
    except Exception:
        pass


@pytest.fixture
def ssh_server():
    key = paramiko.RSAKey.generate(2048)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    threading.Thread(target=_serve, args=(sock, key), daemon=True).start()
    yield sock.getsockname()[1], key
    sock.close()


def test_ssh_rechaza_host_desconocido_por_defecto(ssh_server, monkeypatch):
    monkeypatch.setenv("ALLOW_UNKNOWN_HOSTS", "false")
    port, _ = ssh_server
    with pytest.raises(TransportError, match="desconocido|known_hosts"):
        SSHSession(ConnectionParams("127.0.0.1", USER, PWD, port)).connect()


def test_ssh_lote_en_modo_laboratorio_y_redacta_secretos(ssh_server, monkeypatch):
    monkeypatch.setenv("ALLOW_UNKNOWN_HOSTS", "true")
    port, _ = ssh_server
    results = list(stream_batch(ConnectionParams("127.0.0.1", USER, PWD, port, timeout=5),
                                ["show clock", "show run | include secret"]))
    assert results[0].command == "# aviso"
    assert "COT" in results[1].output
    assert PWD not in results[2].output and "********" in results[2].output


def test_ssh_contrasena_incorrecta(ssh_server, monkeypatch):
    monkeypatch.setenv("ALLOW_UNKNOWN_HOSTS", "true")
    port, _ = ssh_server
    with pytest.raises(TransportError, match="Autenticación"):
        SSHSession(ConnectionParams("127.0.0.1", USER, "mala", port, timeout=5)).connect()


def test_ssh_puerto_cerrado():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    with pytest.raises(TransportError):
        SSHSession(ConnectionParams("127.0.0.1", USER, PWD, port, timeout=2)).connect()


def test_ssh_parametros_invalidos():
    with pytest.raises(ValidationError):
        ConnectionParams("10.0.0.1; ls", USER, PWD).validated()
    with pytest.raises(ValidationError):
        ConnectionParams("10.0.0.1", USER, "").validated()


# --------------------------------------------------------------------------- #
# Telnet de laboratorio
# --------------------------------------------------------------------------- #
def test_telnet_bloquea_destinos_publicos(monkeypatch):
    monkeypatch.setenv("ENABLE_TELNET_LAB", "true")
    with pytest.raises(ValidationError, match="privadas"):
        ensure_lab_target("8.8.8.8")


def test_telnet_deshabilitado_por_defecto(monkeypatch):
    monkeypatch.delenv("ENABLE_TELNET_LAB", raising=False)
    with pytest.raises(ValidationError, match="deshabilitado"):
        ensure_lab_target("10.0.0.1")


def test_telnet_negocia_iac_y_ejecuta(monkeypatch):
    monkeypatch.setenv("ENABLE_TELNET_LAB", "true")
    srv = socket.socket(); srv.bind(("127.0.0.1", 0)); srv.listen(1)
    port = srv.getsockname()[1]

    def serve():
        c, _ = srv.accept()
        f = c.makefile("rb")

        def line():  # lee una línea ignorando las respuestas IAC del cliente
            raw = f.readline()
            return raw.replace(bytes([IAC, 252, 1]), b"").strip()

        c.sendall(bytes([IAC, DO, 1]) + b"Username: ")
        assert line() == USER.encode(); c.sendall(b"Password: ")
        assert line() == PWD.encode(); c.sendall(b"\r\nSW1#")
        if line() == b"show version":
            c.sendall(b"Cisco IOS Software\r\nSW1#")
        c.close()

    threading.Thread(target=serve, daemon=True).start()
    with TelnetLabSession("127.0.0.1", USER, PWD, port, timeout=3) as tn:
        r = tn.run("show version")
    srv.close()
    assert "Cisco IOS Software" in r.output and "\xff" not in r.output


# --------------------------------------------------------------------------- #
# Simulador (respuestas derivadas del diseño)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("vendor,cmd", [("Cisco", "show ip interface brief"),
                                        ("Huawei", "display ip interface brief"),
                                        ("Fortinet", "get system interface"),
                                        ("MikroTik", "/ip address print")])
def test_simulador_interfaces_desde_el_plan(vendor, cmd, cfg, plan, topo):
    dev = topo.get("R-CORE")
    sim = LabSimulator(plan, topo, dev, vendor, render_device(Ctx(cfg, plan, topo), vendor, dev.id).text)
    out = sim.run(cmd).output
    assert str(plan.link("ISP-EDGE").b_ip) in out


def test_simulador_rutas_ospf_y_ping(cfg, plan, topo):
    dev = topo.get("R-DIST")
    sim = LabSimulator(plan, topo, dev, "Cisco", "")
    assert str(plan.summary_route) in sim.run("show ip route").output
    assert "1.1.1.1" in sim.run("show ip ospf neighbor").output
    assert "!!!!!" in sim.run(f"ping {plan.floor_segments()[0].gateway}").output
    assert "....." in sim.run("ping 203.0.113.99").output


def test_simulador_vlans_de_acceso(cfg, plan, topo):
    dev = topo.by_role("access")[0]
    out = LabSimulator(plan, topo, dev, "Cisco", "").run("show vlan brief").output
    assert "101" in out and "999" in out and "115" not in out


def test_simulador_redacta_running_config(cfg, plan, topo):
    dev = topo.get("R-CORE")
    sim = LabSimulator(plan, topo, dev, "Cisco", "username x secret 9 RealSecret99")
    assert "RealSecret99" not in sim.run("show running-config").output


def test_simulador_valida_comandos(cfg, plan, topo):
    sim = LabSimulator(plan, topo, topo.get("R-CORE"), "Cisco", "")
    with pytest.raises(ValidationError):
        sim.run("show ver; reload")
