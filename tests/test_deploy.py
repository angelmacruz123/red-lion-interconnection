"""M5 · Despliegue guiado: del plan de la app a la terminal del equipo."""

import socket
import threading

import paramiko
import pytest

from core.validators import ValidationError
from generators import ENGINES, render_device
from generators.common import Ctx
from netdevops import deploy
from netdevops.deploy import (CATEGORIES, build_deploy_plan, classify, detect_error, execute,
                              resolve_categories, split_blocks)
from netdevops.simulator import LabSimulator, SimState
from netdevops.ssh_client import ConnectionParams, SSHSession, validate_config_line

VENDORS = list(ENGINES)
BASIC = ["hostname", "vlans", "ip", "ports"]


@pytest.fixture(autouse=True)
def _sin_secretos_y_respaldos_temporales(monkeypatch, tmp_path):
    for env in deploy.SECRET_ENV.values():
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setattr(deploy, "BACKUP_DIR", tmp_path / "backups")


@pytest.fixture
def ctx(cfg, plan, topo):
    return Ctx(cfg, plan, topo)


# --------------------------------------------------------------------------- #
# Partición y clasificación
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("vendor", VENDORS)
def test_bloques_cubren_toda_la_configuracion(vendor, ctx):
    """Ninguna línea útil de la configuración generada se pierde al partir en bloques."""
    text = render_device(ctx, vendor, "SW-CORE").text
    blocks = split_blocks(vendor, text)
    joined = {ln for b in blocks for ln in b}
    comment = "!" if vendor == "Cisco" else "#"
    wrappers = {"end", "write memory", "system-view", "return", "save"}
    useful = [ln.rstrip() for ln in text.splitlines()
              if ln.strip() and not ln.strip().startswith(comment) and ln.strip() not in wrappers]
    if vendor == "Fortinet":
        useful = [ln for ln in useful if ln.strip() != "end" or ln.startswith(" ")]
    assert set(useful) - joined <= {"end"}


@pytest.mark.parametrize("vendor", VENDORS)
def test_hostname_vlans_e_ip_se_clasifican(vendor, ctx, topo):
    dev = topo.get("SW-ACC-P01-1")
    blocks = classify(vendor, split_blocks(vendor, render_device(ctx, vendor, dev.id).text))
    cats = {b.category for b in blocks}
    assert {"vlans", "ip", "ports", "seguridad"} <= cats
    if vendor != "Fortinet":  # en FortiSwitch el nombre se sintetiza en un bloque propio
        host_blocks = [b for b in blocks if b.category == "hostname"]
        assert len(host_blocks) == 1 and dev.hostname in host_blocks[0].header


def test_dependencias_se_agregan_en_switches():
    cats, notes = resolve_categories(["ip"], "access")
    assert cats == ["vlans", "ip"] and notes
    cats, _ = resolve_categories(["ip"], "edge")
    assert cats == ["ip"]
    cats, _ = resolve_categories(["routing"], "core")
    assert cats == ["vlans", "ip", "routing"]


# --------------------------------------------------------------------------- #
# Plan de despliegue
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("vendor", VENDORS)
@pytest.mark.parametrize("device", ["R-CORE", "R-DIST", "SW-CORE", "SW-ACC-P01-1", "SW-SRV"])
def test_plan_basico_para_todos_los_equipos(vendor, device, ctx, plan):
    dp = build_deploy_plan(ctx, vendor, device, BASIC)
    assert dp.blocks and dp.hostname in dp.preview()
    assert not any("<<" in ln for ln in dp.body_lines)            # nunca marcadores al equipo
    text = "\n".join(dp.body_lines)
    if device == "SW-CORE":
        assert str(plan.floor_segments()[0].gateway) in text      # SVIs del plan
    if device == "R-CORE":
        assert str(plan.link("ISP-EDGE").b_ip) in text            # IP WAN del plan


def test_ip_sin_servicios_quita_nat_y_acl(ctx):
    dp = build_deploy_plan(ctx, "Cisco", "R-CORE", ["ip"])
    text = "\n".join(dp.body_lines)
    assert "ip address 200.10.10.2" in text
    for dependent in ("ip nat", "ip access-group", "service-policy", "ip ospf"):
        assert dependent not in text


def test_puertos_encendidos_y_sin_uso_apagados(ctx):
    dp = build_deploy_plan(ctx, "Cisco", "SW-ACC-P01-2", ["ports"])
    text = "\n".join(dp.body_lines)
    assert "no shutdown" in text and "switchport access vlan 101" in text
    assert "NO-USADO" in text and "\n shutdown" in text


def test_hardening_bloqueado_sin_secretos(ctx):
    with pytest.raises(ValidationError, match="ADMIN_SECRET"):
        build_deploy_plan(ctx, "Cisco", "R-CORE", ["seguridad"])


def test_hardening_con_secretos_del_env(ctx, monkeypatch):
    monkeypatch.setenv("ADMIN_SECRET", "Adm1n-Lab-2026")
    monkeypatch.setenv("ENABLE_SECRET", "En4ble-Lab-2026")
    dp = build_deploy_plan(ctx, "Cisco", "R-CORE", ["seguridad"])
    assert "Adm1n-Lab-2026" not in dp.preview()                  # la vista previa nunca muestra secretos
    assert "<<ADMIN_SECRET>>" in dp.preview()


def test_vpn_sin_peer_se_omite(ctx):
    dp = build_deploy_plan(ctx, "Cisco", "R-CORE", ["servicios"])
    assert any("PEER_PUBLIC_IP" in s for s in dp.skipped)


def test_categoria_invalida(ctx):
    with pytest.raises(ValidationError):
        build_deploy_plan(ctx, "Cisco", "R-CORE", ["borrar_todo"])


def test_sin_guardar_no_envia_write_memory(ctx):
    dp = build_deploy_plan(ctx, "Cisco", "R-DIST", ["hostname"], save=False)
    assert dp.post == ["end"]


# --------------------------------------------------------------------------- #
# Ejecución contra el simulador
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("vendor", VENDORS)
def test_simulador_pasa_de_fabrica_a_configurado(vendor, ctx, plan, topo):
    dev = topo.get("SW-CORE")
    state = SimState.factory(vendor, dev)
    sim = LabSimulator(plan, topo, dev, vendor, render_device(ctx, vendor, dev.id).text, state)
    assert dev.hostname not in sim.prompt()
    dp = build_deploy_plan(ctx, vendor, dev.id, BASIC)
    steps = list(execute(dp, sim, secrets={}))
    assert all(s.ok for s in steps)
    assert [s.phase for s in steps][0] == "backup" and steps[-1].phase == "verify"
    assert dev.hostname in sim.prompt()
    assert {"hostname", "vlans", "ip", "ports"} <= state.applied
    verify = "\n".join(s.output for s in steps if s.phase == "verify")
    assert str(plan.floor_segments()[0].gateway) in verify


def test_respaldo_se_guarda(ctx, plan, topo, tmp_path):
    dev = topo.get("R-DIST")
    sim = LabSimulator(plan, topo, dev, "Cisco", "", SimState.factory("Cisco", dev))
    steps = list(execute(build_deploy_plan(ctx, "Cisco", dev.id, ["hostname"]), sim, secrets={}))
    assert "Respaldo guardado" in steps[0].output
    assert len(list((tmp_path / "backups").glob("*.txt"))) == 1


@pytest.mark.parametrize("vendor,text", [("Cisco", "% Invalid input detected at '^' marker."),
                                         ("Huawei", "Error: Unrecognized command found at '^' position."),
                                         ("Fortinet", "Command fail. Return code -61"),
                                         ("MikroTik", "bad command name foo (line 1 column 1)")])
def test_deteccion_de_errores_por_fabricante(vendor, text):
    assert detect_error(vendor, text)


def test_detenerse_en_error_no_guarda(ctx, plan, topo):
    class Fallido(LabSimulator):
        sent = []

        def send_lines(self, lines):
            self.sent.extend(lines)
            if any(l.startswith("interface") for l in lines):
                return "% Invalid input detected at '^' marker."
            return super().send_lines(lines)

    dev = topo.get("R-DIST")
    sim = Fallido(plan, topo, dev, "Cisco", "", SimState.factory("Cisco", dev))
    steps = list(execute(build_deploy_plan(ctx, "Cisco", dev.id, ["hostname", "ip"]), sim, secrets={}))
    assert steps[-1].phase == "info" and not steps[-1].ok
    assert "write memory" not in sim.sent and "end" in sim.sent


def test_linea_de_configuracion_validada():
    with pytest.raises(ValidationError):
        validate_config_line("hostname R1\nreload")
    with pytest.raises(ValidationError):
        validate_config_line("username a secret <<ADMIN_SECRET>>")
    assert validate_config_line(" ip address 10.0.0.1 255.255.255.0")


# --------------------------------------------------------------------------- #
# Ejecución real por SSH contra un IOS emulado (modo usuario → enable → config)
# --------------------------------------------------------------------------- #
USER, PWD, ENA = "netadmin", "LabPass123", "Enable123"


class _IOS(paramiko.ServerInterface):
    def check_auth_password(self, u, p):
        return paramiko.AUTH_SUCCESSFUL if (u, p) == (USER, PWD) else paramiko.AUTH_FAILED

    def get_allowed_auths(self, u):
        return "password"

    def check_channel_request(self, kind, cid):
        return paramiko.OPEN_SUCCEEDED

    def check_channel_pty_request(self, *a):
        return True

    def check_channel_shell_request(self, ch):
        return True


def _serve_ios(sock, key, log):
    conn, _ = sock.accept()
    t = paramiko.Transport(conn)
    t.add_server_key(key)
    t.start_server(server=_IOS())
    ch = t.accept(5)
    host, mode = "Router", "user"

    def prompt():
        return {"user": f"{host}>", "priv": f"{host}#", "conf": f"{host}(config)#",
                "if": f"{host}(config-if)#"}[mode]

    ch.send(prompt())
    buf = ""
    try:
        while True:
            data = ch.recv(1024)
            if not data:
                break
            buf += data.decode()
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                cmd = line.strip()
                log.append(cmd)
                out = ""
                if mode == "user" and cmd == "enable":
                    ch.send("Password: ")
                    mode = "enable_pwd"
                    continue
                if mode == "enable_pwd":
                    mode = "priv" if cmd == ENA else "user"
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
                elif cmd.startswith("bad"):
                    out = "% Invalid input detected at '^' marker.\r\n"
                ch.send(out + prompt())
    except Exception:
        pass


@pytest.fixture
def ios_server(monkeypatch):
    monkeypatch.setenv("ALLOW_UNKNOWN_HOSTS", "true")
    key = paramiko.RSAKey.generate(2048)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    log: list[str] = []
    threading.Thread(target=_serve_ios, args=(sock, key, log), daemon=True).start()
    yield sock.getsockname()[1], log
    sock.close()


def test_despliegue_ssh_completo(ios_server, ctx):
    port, log = ios_server
    dp = build_deploy_plan(ctx, "Cisco", "R-DIST", ["hostname", "ip"])
    with SSHSession(ConnectionParams("127.0.0.1", USER, PWD, port, "Cisco", timeout=5)) as s:
        s.ensure_privileged(ENA)
        steps = list(execute(dp, s, secrets={}))
    assert all(st.ok for st in steps), [st.output for st in steps if not st.ok]
    assert "configure terminal" in log and "write memory" in log
    assert f"hostname {ctx.topo.get('R-DIST').hostname}" in log
    assert any(l.startswith("ip address 172.31.255.2") for l in log)
    assert ENA not in "".join(st.output for st in steps)


def test_despliegue_ssh_se_detiene_ante_error(ios_server, ctx):
    port, log = ios_server
    dp = build_deploy_plan(ctx, "Cisco", "R-DIST", ["hostname"])
    dp.blocks.insert(1, deploy.Block("ip", ["bad command here"]))
    with SSHSession(ConnectionParams("127.0.0.1", USER, PWD, port, "Cisco", timeout=5)) as s:
        s.ensure_privileged(ENA)
        steps = list(execute(dp, s, backup=False, verify=False, secrets={}))
    assert not steps[-1].ok and "write memory" not in log
