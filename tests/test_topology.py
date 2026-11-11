"""M3 · Topología: el grafo refleja la jerarquía y usa solo datos del plan."""

from core.state import ProjectConfig
from core.ipam import build_address_plan
from core.topology import build_topology, to_dot, to_mermaid


def test_jerarquia_completa(topo):
    pairs = {(e.a, e.b) for e in topo.edges}
    assert ("ISP", "R-CORE") in pairs
    assert ("R-CORE", "R-DIST") in pairs
    assert ("R-DIST", "SW-CORE") in pairs
    assert all(("SW-CORE", d.id) in pairs for d in topo.by_role("access"))
    assert ("SW-CORE", "SW-SRV") in pairs and ("R-CORE", "DMZ") in pairs


def test_cada_piso_tiene_acceso(cfg, topo):
    floors = {d.floor for d in topo.by_role("access")}
    assert floors == set(range(1, cfg.floors + 1))


def test_ips_de_gestion_unicas_y_en_vlan_99(plan, topo):
    ips = [d.mgmt_ip for d in topo.devices if d.mgmt_ip]
    assert len(ips) == len(set(ips))
    mgmt = plan.segment("mgmt").network
    import ipaddress
    assert all(ipaddress.IPv4Address(ip) in mgmt for ip in ips)


def test_etiquetas_de_enlaces_salen_del_plan(plan, topo):
    labels = " ".join(e.label for e in topo.edges)
    for link in plan.links:
        assert str(link.network) in labels


def test_dot_y_mermaid_validos(topo):
    dot = to_dot(topo, 'Proyecto "con comillas"')
    assert dot.startswith("digraph G {") and dot.rstrip().endswith("}")
    assert '\\"con comillas\\"' in dot
    mmd = to_mermaid(topo)
    assert mmd.startswith("flowchart LR") and "PISO_01" and "R_CORE" in mmd


def test_switches_extra_si_el_piso_supera_48_puertos():
    cfg = ProjectConfig(floors=2, hosts_total=200)  # 125 hosts/piso con crecimiento
    plan = build_address_plan(cfg)
    topo = build_topology(cfg, plan)
    assert len([d for d in topo.by_role("access") if d.floor == 1]) == 3


def test_ssl_vpn_dibuja_usuarios_remotos():
    cfg = ProjectConfig(vpn_type="SSL")
    plan = build_address_plan(cfg)
    topo = build_topology(cfg, plan)
    assert topo.get("REMOTO").hostname == "USUARIOS-REMOTOS"
