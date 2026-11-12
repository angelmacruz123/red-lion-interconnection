"""M6 · Advertencia de configuraciones inseguras (mínimo privilegio)."""

import pytest

from core.ipam import build_address_plan
from core.security_audit import INSECURE_SAMPLE, audit, summary
from core.state import VPN_TYPES, ProjectConfig
from core.topology import build_topology
from generators import ENGINES, render_all
from generators.common import Ctx, device_summary


def rules(text):
    return {f.rule for f in audit(text)}


@pytest.mark.parametrize("vendor", list(ENGINES))
@pytest.mark.parametrize("vpn", VPN_TYPES)
def test_configuraciones_generadas_sin_riesgos(vendor, vpn):
    cfg = ProjectConfig(vpn_type=vpn)
    plan = build_address_plan(cfg)
    for c in render_all(cfg, plan, build_topology(cfg, plan), vendor):
        risky = [f for f in audit(c.text) if f.severity in ("alta", "media")]
        assert not risky, (c.filename, risky[:2])


def test_ejemplo_inseguro_detecta_todo():
    found = rules(INSECURE_SAMPLE)
    assert {"telnet", "cred-default", "cleartext", "http", "snmp", "permit-any", "vty-acl"} <= found
    assert summary(audit(INSECURE_SAMPLE))["alta"] >= 4


@pytest.mark.parametrize("line,rule", [
    ("line vty 0 4\n transport input all\n access-class A in\n exec-timeout 5 0", "telnet"),
    ("telnet server enable", "telnet"),
    ("user-interface vty 0 4\n protocol inbound telnet", "telnet"),
    ('edit "port2"\n    set allowaccess ping telnet https\nnext', "telnet"),
    ("/ip service enable telnet", "telnet"),
    ("ip ssh version 1", "ssh-v1"),
    ("snmp-agent community read public", "snmp"),
    ("/snmp community add name=public", "snmp"),
    ("snmp-server community Lab123 RW", "snmp"),
    ("local-user admin password simple admin", "cred-default"),
    ('/user add name=admin password="admin" group=full', "cred-default"),
    ("aaa\n local-user ops password simple Zx9!kq7", "cleartext"),
    (" 10 permit ip any any", "permit-any"),
])
def test_reglas_por_fabricante(line, rule):
    assert rule in rules(line)


@pytest.mark.parametrize("line", [
    "undo telnet server enable",
    "transport input ssh",
    "ip ssh version 2",
    "snmp-server group NETOPS v3 priv",
    "/ip service disable telnet,ftp,www,api,api-ssl",
    "! transport input telnet",
])
def test_lineas_seguras_no_alertan(line):
    risky = [f for f in audit(line) if f.severity in ("alta", "media")]
    assert not risky, risky


def test_fortinet_wan_administrable_y_politica_todo():
    text = ('config system interface\n    edit "wan1"\n        set allowaccess ping https ssh\n    next\nend\n'
            'config firewall policy\n    edit 9\n        set srcaddr "all"\n        set dstaddr "all"\n'
            '        set action accept\n        set service "ALL"\n    next\nend')
    assert {"mgmt-wan", "permit-any"} <= rules(text)


def test_mikrotik_admin_de_fabrica_activo():
    assert "cred-default" in rules('/user add name=ops group=full password="Xk2!pq9z"')
    assert "cred-default" not in rules('/user add name=ops group=full password="Xk2!pq9z"\n/user set admin disabled=yes')


def test_hallazgos_ordenados_por_severidad():
    sev = [f.severity for f in audit(INSECURE_SAMPLE)]
    order = {"alta": 0, "media": 1, "baja": 2}
    assert sev == sorted(sev, key=order.get)


def test_resumen_del_equipo_hostname_vlan_ip(cfg, plan, topo):
    ctx = Ctx(cfg, plan, topo)
    vlans, ips = device_summary(ctx, topo.get("SW-CORE"))
    assert 101 in vlans and 99 in vlans
    assert ("P2P-R-DIST", f"{plan.link('DIST-CORESW').b_ip}/30") in ips
    vlans, ips = device_summary(ctx, topo.by_role("access")[0])
    assert 101 in vlans and ips[0][1].startswith(topo.by_role("access")[0].mgmt_ip)
