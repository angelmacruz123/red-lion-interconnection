"""M3 · Carga de topología: ingresar, importar, validar y que alimente las configuraciones."""

import copy
import json

import pytest

from core import topology_io as tio
from core.topology import build_topology, to_dot
from core.validators import ValidationError
from generators import render_all, render_device
from generators.common import Ctx


@pytest.fixture
def tables(topo):
    return tio.topology_to_tables(topo)


def _build(cfg, plan, topo, devices, links):
    return tio.build_from_tables(cfg, plan, topo, devices, links)


def test_exportar_e_importar_json_es_identico(cfg, plan, topo):
    devices, links = tio.from_json(tio.to_json(topo))
    new = _build(cfg, plan, topo, devices, links)
    assert [(d.id, d.hostname, d.mgmt_ip) for d in new.devices] == [(d.id, d.hostname, d.mgmt_ip) for d in topo.devices]
    assert {(e.a, e.b, e.label) for e in new.edges} == {(e.a, e.b, e.label) for e in topo.edges}


def test_importar_csv(cfg, plan, topo):
    devices = tio.from_csv(tio.devices_csv(topo), tio.DEVICE_COLUMNS)
    links = tio.from_csv(tio.links_csv(topo), tio.LINK_COLUMNS)
    assert len(_build(cfg, plan, topo, devices, links).devices) == len(topo.devices)


def test_renombrar_equipo_cambia_la_configuracion(cfg, plan, topo, tables):
    devices, links = copy.deepcopy(tables)
    next(d for d in devices if d["id"] == "R-DIST")["hostname"] = "BOG-DIST-01"
    new = _build(cfg, plan, topo, devices, links)
    text = render_device(Ctx(cfg, plan, new), "Cisco", "R-DIST").text
    assert "hostname BOG-DIST-01" in text


def test_agregar_router_y_enlace_wan_asigna_30_y_configura(cfg, plan, topo, tables):
    devices, links = copy.deepcopy(tables)
    devices.append({"id": "R-SEDE2", "hostname": "MED-R-01", "rol": "router", "piso": "", "ip_gestion": "10.20.6.200"})
    links.append({"origen": "R-SEDE2", "destino": "R-CORE", "tipo": "wan"})
    new = _build(cfg, plan, topo, devices, links)
    assert len(new.extra_links) == 1
    link = new.extra_links[0]
    assert link.network.prefixlen == 30 and link.a_device == "R-CORE"
    used = [l.network for l in plan.links] + [plan.tunnel.network]
    assert not any(link.network.overlaps(u) for u in used)
    for vendor in ("Cisco", "Huawei", "Fortinet", "MikroTik"):
        configs = {c.device_id: c.text for c in render_all(cfg, plan, new, vendor)}
        assert str(link.a_ip) in configs["R-CORE"] and str(link.b_ip) in configs["R-SEDE2"]
        assert "MED-R-01" in configs["R-SEDE2"]
    assert configs["R-CORE"].rstrip().split("\n")[-1] != ""  # MikroTik sin trailer
    cisco = render_device(Ctx(cfg, plan, new), "Cisco", "R-CORE").text
    assert cisco.rstrip().endswith("write memory")  # el enlace nuevo va ANTES de guardar
    assert f"WAN {link.network}" in to_dot(new)


def test_agregar_switch_de_acceso_reparte_puertos(cfg, plan, topo, tables):
    devices, links = copy.deepcopy(tables)
    devices.append({"id": "SW-ACC-P01-3", "hostname": "TCB-SW-ACC-P01-3", "rol": "access", "piso": "1",
                    "ip_gestion": "10.20.6.210"})
    links.append({"origen": "SW-ACC-P01-3", "destino": "SW-CORE", "tipo": "trunk"})  # al revés: se normaliza
    new = _build(cfg, plan, topo, devices, links)
    assert any(e.a == "SW-CORE" and e.b == "SW-ACC-P01-3" and "101" in e.label for e in new.edges)
    core = render_device(Ctx(cfg, plan, new), "Cisco", "SW-CORE").text
    assert "TRUNK-TCB-SW-ACC-P01-3" in core


@pytest.mark.parametrize("mutate,expected", [
    (lambda d, l: d.append({"id": "X", "hostname": "bad host", "rol": "router", "piso": "", "ip_gestion": "10.20.6.201"}), "Hostname inválido"),
    (lambda d, l: d.append({"id": "Y", "hostname": "Y1", "rol": "firewall", "piso": "", "ip_gestion": ""}), "rol 'firewall'"),
    (lambda d, l: d.append({"id": "Z", "hostname": "Z1", "rol": "router", "piso": "", "ip_gestion": "8.8.8.8"}), "debe estar dentro"),
    (lambda d, l: d.append({"id": "W", "hostname": "W1", "rol": "access", "piso": "99", "ip_gestion": "10.20.6.202"}), "piso entre 1"),
    (lambda d, l: l.append({"origen": "R-CORE", "destino": "NO-EXISTE", "tipo": "wan"}), "no existe"),
    (lambda d, l: l.append({"origen": "R-CORE", "destino": "R-CORE", "tipo": "p2p"}), "consigo mismo"),
    (lambda d, l: l.append({"origen": "R-CORE", "destino": "R-DIST", "tipo": "p2p"}), "duplicado"),
    (lambda d, l: l.append({"origen": "R-CORE", "destino": "SW-SRV", "tipo": "satelite"}), "tipo 'satelite'"),
    (lambda d, l: d.__setitem__(1, {**d[1], "hostname": d[2]["hostname"]}), "repetido"),
    (lambda d, l: d.__setitem__(1, {**d[1], "ip_gestion": d[2]["ip_gestion"]}), "IP de gestión repetida"),
    (lambda d, l: d.__setitem__(1, {**d[1], "ip_gestion": "10.20.6.129"}), "gateway de gestión"),
])
def test_validacion_rechaza_errores(cfg, plan, topo, tables, mutate, expected):
    devices, links = copy.deepcopy(tables)
    mutate(devices, links)
    with pytest.raises(ValidationError, match=expected):
        _build(cfg, plan, topo, devices, links)


def test_columna_vertebral_obligatoria(cfg, plan, topo, tables):
    devices, links = copy.deepcopy(tables)
    devices = [d for d in devices if d["id"] != "R-DIST"]
    links = [l for l in links if "R-DIST" not in (l["origen"], l["destino"])]
    with pytest.raises(ValidationError, match="rol 'dist'"):
        _build(cfg, plan, topo, devices, links)


def test_acceso_sin_troncal_rechazado(cfg, plan, topo, tables):
    devices, links = copy.deepcopy(tables)
    links = [l for l in links if l["destino"] != "SW-ACC-P01-1"]
    with pytest.raises(ValidationError, match="falta el enlace troncal"):
        _build(cfg, plan, topo, devices, links)


def test_todos_los_errores_juntos(cfg, plan, topo, tables):
    devices, links = copy.deepcopy(tables)
    devices[1]["hostname"] = "mal nombre"
    devices[2]["ip_gestion"] = "1.1.1.1"
    with pytest.raises(ValidationError) as exc:
        _build(cfg, plan, topo, devices, links)
    assert str(exc.value).count("\n") >= 1


@pytest.mark.parametrize("payload", [b"no es json", b'{"dispositivos": 3}', b"\xff\xfe\x00"])
def test_json_invalido(payload):
    with pytest.raises(ValidationError):
        tio.from_json(payload)


def test_csv_sin_columnas():
    with pytest.raises(ValidationError, match="Faltan columnas"):
        tio.from_csv("a,b\n1,2\n", tio.DEVICE_COLUMNS)


def test_archivo_demasiado_grande():
    with pytest.raises(ValidationError, match="512 KB"):
        tio.from_json(b"x" * (600 * 1024))
