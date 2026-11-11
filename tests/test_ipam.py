"""M2 · Planificación IP: matemática de subredes verificada contra cálculos manuales."""

import ipaddress
import itertools

import pytest

from core.ipam import (P2PLink, build_address_plan, ipv6_for_vlan, prefix_for_hosts, with_growth)
from core.state import ProjectConfig
from core.validators import ValidationError


@pytest.mark.parametrize("hosts,prefix", [(1, 29), (6, 29), (7, 28), (14, 28), (30, 27), (50, 26),
                                          (62, 26), (63, 25), (126, 25), (254, 24), (510, 23), (750, 22)])
def test_prefijo_minimo_para_hosts(hosts, prefix):
    assert prefix_for_hosts(hosts) == prefix


def test_crecimiento_redondea_hacia_arriba():
    assert with_growth(40, 25) == 50
    assert with_growth(41, 25) == 52


def test_escenario_15_pisos_genera_un_26_por_piso(plan):
    floors = plan.floor_segments()
    assert len(floors) == 15
    assert all(s.prefix == 26 for s in floors)
    assert [s.vlan for s in floors] == list(range(101, 116))


def test_calculo_manual_de_un_26(plan):
    s = plan.floor_segments()[0]
    net = ipaddress.IPv4Network("10.20.7.0/26")
    assert s.network == net
    assert str(s.mask) == "255.255.255.192"
    assert str(s.wildcard) == "0.0.0.63"
    assert str(s.gateway) == "10.20.7.1"
    assert str(s.last_host) == "10.20.7.62"
    assert str(s.broadcast) == "10.20.7.63"
    assert s.usable == 62


def test_ninguna_subred_se_solapa(plan):
    for a, b in itertools.combinations(plan.segments, 2):
        assert not a.network.overlaps(b.network), (a.name, b.name)


def test_todas_las_subredes_caben_en_la_base(plan):
    assert all(s.network.subnet_of(plan.base_v4) for s in plan.segments)


def test_vlsm_alineado_a_frontera(plan):
    for s in plan.segments:
        assert int(s.network.network_address) % s.network.num_addresses == 0


def test_cada_segmento_aloja_sus_hosts(plan):
    assert all(s.usable >= s.hosts_required for s in plan.segments)


def test_enlaces_wan_son_30_estrictos(plan):
    for link in plan.links + [plan.tunnel]:
        assert link.network.prefixlen == 30
        assert link.network.num_addresses == 4
        hosts = list(link.network.hosts())
        assert hosts == [link.a_ip, link.b_ip]          # exactamente 2 IP útiles
        assert link.broadcast == link.network.broadcast_address


def test_enlaces_wan_contiguos_sin_desperdicio(plan):
    internos = [l for l in plan.links if not l.provider_managed] + [plan.tunnel]
    starts = [int(l.network.network_address) for l in internos]
    assert starts == [starts[0] + 4 * i for i in range(len(starts))]


def test_ipv6_un_64_unico_por_vlan(plan):
    nets = [s.ipv6 for s in plan.segments]
    assert all(n.prefixlen == 64 for n in nets)
    assert len(set(nets)) == len(nets)
    assert str(plan.floor_segments()[0].ipv6) == "2001:db8:acad:101::/64"


def test_ipv6_p2p_127(plan):
    for link in plan.links:
        assert link.ipv6.prefixlen == 127
        assert link.a_ip6 != link.b_ip6


def test_ipv6_bloque_56_usa_vlan_decimal():
    net = ipv6_for_vlan(ipaddress.IPv6Network("2001:db8:0:100::/56"), 101)
    assert net.prefixlen == 64 and net.subnet_of(ipaddress.IPv6Network("2001:db8:0:100::/56"))


def test_ruta_sumarizada_cubre_todo(plan):
    assert all(s.network.subnet_of(plan.summary_route) for s in plan.segments)


def test_base_insuficiente_falla_con_mensaje_claro():
    cfg = ProjectConfig(ipv4_base="192.168.1.0/24", hosts_total=600)
    with pytest.raises(ValidationError, match="no alcanza"):
        build_address_plan(cfg)


def test_bloque_wan_no_puede_solapar_lan():
    cfg = ProjectConfig(wan_block="10.20.255.0/24")
    with pytest.raises(ValidationError, match="solaparse"):
        build_address_plan(cfg)


@pytest.mark.parametrize("floors,hosts", [(1, 10), (3, 120), (8, 1600), (40, 4000)])
def test_escalabilidad_multiples_escenarios(floors, hosts):
    plan = build_address_plan(ProjectConfig(floors=floors, hosts_total=hosts))
    assert len(plan.floor_segments()) == floors
    for a, b in itertools.combinations(plan.segments, 2):
        assert not a.network.overlaps(b.network)


def test_servicios_opcionales_se_omiten():
    plan = build_address_plan(ProjectConfig(services=[], vpn_type="Ninguna"))
    roles = {s.role for s in plan.segments}
    assert roles == {"data", "mgmt"}
    assert plan.tunnel is None


def test_p2p_link_propiedades():
    l = P2PLink("X", "A", "B", ipaddress.IPv4Network("172.31.255.12/30"))
    assert (str(l.a_ip), str(l.b_ip), l.mask) == ("172.31.255.13", "172.31.255.14", "255.255.255.252")
