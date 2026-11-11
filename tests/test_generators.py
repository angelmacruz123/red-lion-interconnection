"""M4 · Generadores: los 4 fabricantes producen configuraciones completas y seguras."""

import io
import re
import zipfile

import pytest

from core.ipam import build_address_plan
from core.state import VPN_TYPES, ProjectConfig
from core.topology import build_topology
from generators import ENGINES, Extras, bundle_zip, render_all
from generators.common import port_plan, Ctx

VENDORS = list(ENGINES)


@pytest.mark.parametrize("vendor", VENDORS)
def test_un_archivo_por_equipo(vendor, cfg, plan, topo):
    configs = render_all(cfg, plan, topo, vendor)
    expected = [d for d in topo.devices if d.role in ("edge", "dist", "core", "access", "server")]
    assert len(configs) == len(expected)
    assert len({c.filename for c in configs}) == len(configs)
    assert all(c.filename.endswith(".txt") for c in configs)


@pytest.mark.parametrize("vendor", VENDORS)
def test_ips_del_plan_aparecen_en_las_configs(vendor, cfg, plan, topo):
    text = "\n".join(c.text for c in render_all(cfg, plan, topo, vendor))
    for link in plan.links:
        assert str(link.b_ip) in text
    for seg in plan.floor_segments():
        assert str(seg.gateway) in text


@pytest.mark.parametrize("vendor", VENDORS)
@pytest.mark.parametrize("vpn", VPN_TYPES)
def test_todos_los_tipos_de_vpn(vendor, vpn):
    cfg = ProjectConfig(vpn_type=vpn)
    plan = build_address_plan(cfg)
    configs = render_all(cfg, plan, build_topology(cfg, plan), vendor)
    edge = configs[0].text
    if vpn == "IPsec":
        assert "<<VPN_PSK>>" in edge
    if vpn == "MPLS":
        assert "65000" in edge


SECRET_WORDS = re.compile(r"(?i)\b(secret|password|psksecret|passwd|pre-shared-key|priv-pwd|auth-pwd)\b")
NON_SECRET_LINES = ("service password-encryption", "security passwords min-length",
                    "password-force-change", "authentication-type password")


@pytest.mark.parametrize("vendor", VENDORS)
def test_sin_secretos_reales_solo_marcadores(vendor, cfg, plan, topo):
    """Toda línea que asigna un secreto debe usar un marcador <<...>>."""
    for c in render_all(cfg, plan, topo, vendor):
        for line in c.text.splitlines():
            if line.lstrip().startswith(("!", "#")) or any(x in line for x in NON_SECRET_LINES):
                continue
            if SECRET_WORDS.search(line):
                assert "<<" in line, f"{c.filename}: {line.strip()}"


def test_parametros_remotos_reemplazan_marcadores(cfg, plan, topo):
    ex = Extras(peer_public_ip="190.85.10.20", remote_lan="10.50.0.0/16")
    edge = render_all(cfg, plan, topo, "Cisco", ex)[0].text
    assert "<<PEER_PUBLIC_IP>>" not in edge and "190.85.10.20" in edge
    assert "ip route 10.50.0.0 255.255.0.0 Tunnel0" in edge


def test_cisco_acceso_endurecido(cfg, plan, topo):
    access = next(c for c in render_all(cfg, plan, topo, "Cisco") if c.role == "access")
    for needle in ("transport input ssh", "spanning-tree bpduguard enable", "switchport port-security",
                   "ip dhcp snooping", "switchport trunk native vlan 999", "shutdown"):
        assert needle in access.text


def test_huawei_usa_sintaxis_vrp(cfg, plan, topo):
    core = next(c for c in render_all(cfg, plan, topo, "Huawei") if c.role == "core")
    assert "vlan batch" in core.text and "interface Vlanif101" in core.text and "ip pool" in core.text


def test_fortinet_politicas_explicitas(cfg, plan, topo):
    edge = render_all(cfg, plan, topo, "Fortinet")[0].text
    assert "config firewall policy" in edge and "set nat enable" in edge


def test_mikrotik_vlan_filtering_al_final(cfg, plan, topo):
    for c in render_all(cfg, plan, topo, "MikroTik"):
        if c.role in ("core", "access", "server"):
            assert c.text.rstrip().endswith("vlan-filtering=yes")


def test_plan_de_puertos_no_excede_48(cfg, plan, topo):
    ctx = Ctx(cfg, plan, topo)
    for d in topo.by_role("access"):
        groups = port_plan(ctx, d)
        assert groups[0].start == 1 and groups[-1].end == 48
        assert sum(g.count for g in groups) == 48


def test_zip_contiene_todos_los_archivos(cfg, plan, topo):
    configs = render_all(cfg, plan, topo, "Cisco")
    with zipfile.ZipFile(io.BytesIO(bundle_zip(configs))) as zf:
        assert sorted(zf.namelist()) == sorted(c.filename for c in configs)


def test_fabricante_invalido(cfg, plan, topo):
    with pytest.raises(ValueError):
        render_all(cfg, plan, topo, "Juniper")
