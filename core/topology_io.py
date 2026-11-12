"""
core/topology_io.py
===================
Módulo 3 — Carga de la topología: ingresar, editar, importar y exportar.

La herramienta propone una topología jerárquica a partir del plan IP, pero el
usuario puede cargar la suya (editar las tablas en pantalla o importar un
archivo JSON/CSV). Lo cargado reemplaza a la topología propuesta y alimenta el
diagrama, las configuraciones de las 4 marcas y el despliegue.

Formato JSON:
    {"dispositivos": [{"id": "R-CORE", "hostname": "TCB-R-CORE", "rol": "edge",
                       "piso": "", "ip_gestion": "10.20.6.130"}, …],
     "enlaces":      [{"origen": "ISP", "destino": "R-CORE", "tipo": "p2p"}, …]}

Formato CSV: un archivo de dispositivos (columnas id,hostname,rol,piso,ip_gestion)
y otro de enlaces (columnas origen,destino,tipo).

Reglas de validación (fail-closed, todos los errores se informan juntos):
* Roles permitidos: isp, edge, dist, core, access, server, dmz, remote, router.
* Debe existir exactamente un isp, un edge (R-CORE), un dist (R-DIST) y un core
  (SW-CORE): las configuraciones y el plan IP dependen de esa columna vertebral.
* Hostname RFC 1123 y único; IP de gestión dentro de la VLAN 99 y única.
* Switches de acceso con piso entre 1 y el número de pisos del diseño.
* Enlaces entre dispositivos existentes, sin bucles a sí mismos ni duplicados.
* Un enlace tipo "wan" entre routers recibe automáticamente un /30 del bloque
  WAN (sin solaparse con los ya usados) y su configuración en las 4 marcas.
"""

from __future__ import annotations

import csv
import io
import ipaddress
import json
import re
from dataclasses import replace

from .ipam import AddressPlan, P2PLink
from .state import ProjectConfig
from .topology import Device, Edge, Topology
from .validators import ValidationError, validate_hostname

ROLES = {
    "isp": "Borde",
    "edge": "Borde",
    "dist": "Distribución",
    "core": "Núcleo",
    "access": "Acceso",
    "server": "Servicios",
    "dmz": "Servicios",
    "remote": "Borde",
    "router": "Borde",       # router adicional (otra sede, segundo borde, laboratorio)
}
LINK_TYPES = ("p2p", "trunk", "vpn", "wan")
ROUTER_ROLES = ("edge", "dist", "router")
SINGLETONS = {"isp": "ISP", "edge": "R-CORE", "dist": "R-DIST", "core": "SW-CORE"}
NO_MGMT_ROLES = ("isp", "dmz", "remote")
DEVICE_COLUMNS = ("id", "hostname", "rol", "piso", "ip_gestion")
LINK_COLUMNS = ("origen", "destino", "tipo")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-]{0,39}$")
MAX_DEVICES = 400
MAX_LINKS = 800


# --------------------------------------------------------------------------- #
# Exportar
# --------------------------------------------------------------------------- #


def topology_to_tables(topo: Topology) -> tuple[list[dict], list[dict]]:
    devices = [{"id": d.id, "hostname": d.hostname, "rol": d.role,
                "piso": "" if d.floor is None else d.floor, "ip_gestion": d.mgmt_ip or ""}
               for d in topo.devices]
    links = [{"origen": e.a, "destino": e.b, "tipo": e.kind} for e in topo.edges]
    return devices, links


def to_json(topo: Topology) -> str:
    devices, links = topology_to_tables(topo)
    return json.dumps({"dispositivos": devices, "enlaces": links}, ensure_ascii=False, indent=2)


def _csv(rows: list[dict], columns: tuple[str, ...]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(columns), lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({c: r.get(c, "") for c in columns})
    return buf.getvalue()


def devices_csv(topo: Topology) -> str:
    return _csv(topology_to_tables(topo)[0], DEVICE_COLUMNS)


def links_csv(topo: Topology) -> str:
    return _csv(topology_to_tables(topo)[1], LINK_COLUMNS)


# --------------------------------------------------------------------------- #
# Importar
# --------------------------------------------------------------------------- #

MAX_IMPORT_BYTES = 512 * 1024


def _check_size(data: bytes | str) -> str:
    text = data.decode("utf-8-sig", errors="strict") if isinstance(data, bytes) else data
    if len(text.encode()) > MAX_IMPORT_BYTES:
        raise ValidationError("El archivo supera 512 KB.")
    return text


def from_json(data: bytes | str) -> tuple[list[dict], list[dict]]:
    try:
        obj = json.loads(_check_size(data))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"JSON inválido: {exc}") from exc
    if not isinstance(obj, dict) or not isinstance(obj.get("dispositivos"), list) \
            or not isinstance(obj.get("enlaces"), list):
        raise ValidationError("El JSON debe tener las listas 'dispositivos' y 'enlaces'.")
    return obj["dispositivos"], obj["enlaces"]


def from_csv(data: bytes | str, columns: tuple[str, ...]) -> list[dict]:
    try:
        text = _check_size(data)
    except UnicodeDecodeError as exc:
        raise ValidationError("El CSV debe estar en UTF-8.") from exc
    reader = csv.DictReader(io.StringIO(text))
    missing = [c for c in columns if c not in (reader.fieldnames or [])]
    if missing:
        raise ValidationError(f"Faltan columnas en el CSV: {', '.join(missing)}.")
    return [{c: (row.get(c) or "").strip() for c in columns} for row in reader]


# --------------------------------------------------------------------------- #
# Validar y construir
# --------------------------------------------------------------------------- #


def _cell(row: dict, key: str) -> str:
    value = row.get(key, "")
    if value is None or (isinstance(value, float) and value != value):  # NaN de pandas
        return ""
    return str(value).strip()


def build_from_tables(cfg: ProjectConfig, plan: AddressPlan, base: Topology,
                      devices_rows: list[dict], links_rows: list[dict]) -> Topology:
    """Valida las tablas cargadas y devuelve la nueva topología (o ValidationError con TODOS los errores)."""
    errors: list[str] = []
    if not devices_rows:
        raise ValidationError("La topología no tiene dispositivos.")
    if len(devices_rows) > MAX_DEVICES or len(links_rows) > MAX_LINKS:
        raise ValidationError(f"Máximo {MAX_DEVICES} dispositivos y {MAX_LINKS} enlaces.")

    mgmt_net = plan.segment("mgmt").network
    reserved = {str(plan.segment("mgmt").gateway)}
    base_by_id = {d.id: d for d in base.devices}
    devices: list[Device] = []
    seen_ids, seen_hosts, seen_ips = set(), set(), set()

    for n, row in enumerate(devices_rows, start=1):
        dev_id, host = _cell(row, "id"), _cell(row, "hostname")
        role, floor_txt, ip_txt = _cell(row, "rol").lower(), _cell(row, "piso"), _cell(row, "ip_gestion")
        if not dev_id and not host and not role:
            continue  # fila vacía del editor
        where = f"Dispositivo {n} ({dev_id or host or '?'})"
        if not dev_id:
            dev_id = re.sub(r"[^A-Za-z0-9\-]", "-", host).strip("-")[:40]
        if not _ID_RE.fullmatch(dev_id):
            errors.append(f"{where}: id inválido (letras, números y guion).")
            continue
        if dev_id in seen_ids:
            errors.append(f"{where}: id repetido.")
            continue
        seen_ids.add(dev_id)
        if role not in ROLES:
            errors.append(f"{where}: rol '{role}' no válido. Use: {', '.join(ROLES)}.")
            continue
        if role in SINGLETONS and dev_id != SINGLETONS[role]:
            errors.append(f"{where}: el rol '{role}' corresponde al id {SINGLETONS[role]}.")
        try:
            validate_hostname(host)
        except ValidationError as exc:
            errors.append(f"{where}: {exc}")
        if host.upper() in seen_hosts:
            errors.append(f"{where}: hostname repetido '{host}'.")
        seen_hosts.add(host.upper())

        floor = None
        if role == "access":
            try:
                floor = int(float(floor_txt))
                if not 1 <= floor <= cfg.floors:
                    raise ValueError
            except ValueError:
                floor = None
                errors.append(f"{where}: un switch de acceso necesita piso entre 1 y {cfg.floors}.")

        mgmt_ip = ""
        if role not in NO_MGMT_ROLES:
            try:
                ip = ipaddress.IPv4Address(ip_txt)
                if ip not in mgmt_net or ip in (mgmt_net.network_address, mgmt_net.broadcast_address):
                    raise ValueError
                if str(ip) in reserved:
                    errors.append(f"{where}: {ip} es el gateway de gestión, use otra IP.")
                elif str(ip) in seen_ips:
                    errors.append(f"{where}: IP de gestión repetida {ip}.")
                seen_ips.add(str(ip))
                mgmt_ip = str(ip)
            except ValueError:
                errors.append(f"{where}: IP de gestión '{ip_txt}' debe estar dentro de {mgmt_net}.")

        old = base_by_id.get(dev_id)
        details = list(old.details) if old and old.role == role else []
        if role == "access" and floor is not None and not (old and old.floor == floor):
            seg = next(s for s in plan.floor_segments() if s.floor == floor)
            details = [f"VLAN {seg.vlan} · {seg.network}"]
        devices.append(Device(dev_id, host, role, ROLES[role], mgmt_ip, floor, details))

    present = {d.role for d in devices}
    for role, dev_id in SINGLETONS.items():
        count = sum(1 for d in devices if d.role == role)
        if count != 1:
            errors.append(f"Debe existir exactamente un dispositivo con rol '{role}' (id {dev_id}); hay {count}.")
    if "access" not in present:
        errors.append("Debe existir al menos un switch de acceso.")

    ids = {d.id for d in devices}
    by_id = {d.id: d for d in devices}
    edges: list[Edge] = []
    pairs = set()
    for n, row in enumerate(links_rows, start=1):
        a, b, kind = _cell(row, "origen"), _cell(row, "destino"), _cell(row, "tipo").lower() or "p2p"
        if not a and not b:
            continue
        where = f"Enlace {n} ({a} → {b})"
        if a not in ids or b not in ids:
            errors.append(f"{where}: origen o destino no existe en los dispositivos.")
            continue
        if a == b:
            errors.append(f"{where}: un equipo no puede enlazarse consigo mismo.")
            continue
        if kind not in LINK_TYPES:
            errors.append(f"{where}: tipo '{kind}' no válido. Use: {', '.join(LINK_TYPES)}.")
            continue
        key = frozenset((a, b))
        if key in pairs:
            errors.append(f"{where}: enlace duplicado.")
            continue
        pairs.add(key)
        if kind == "wan" and not ({by_id[a].role, by_id[b].role} & set(ROUTER_ROLES)):
            errors.append(f"{where}: un enlace WAN necesita al menos un router (edge, dist o router).")
            continue
        edges.append(Edge(a, b, "", kind))

    # Cada switch de acceso/servidores debe colgar del núcleo para recibir su troncal.
    for d in devices:
        if d.role in ("access", "server") and frozenset(("SW-CORE", d.id)) not in pairs:
            errors.append(f"{d.id}: falta el enlace troncal desde SW-CORE.")

    if errors:
        raise ValidationError("\n".join(errors))

    topo = Topology(devices=devices, edges=[])
    _label_and_allocate(cfg, plan, base, topo, edges)
    return topo


def _label_and_allocate(cfg: ProjectConfig, plan: AddressPlan, base: Topology, topo: Topology,
                        edges: list[Edge]) -> None:
    """Etiqueta cada enlace con datos del plan y asigna /30 a los enlaces WAN nuevos."""
    known = {frozenset((l.a_device, l.b_device)): l for l in plan.links}
    if plan.tunnel:
        known[frozenset((plan.tunnel.a_device, plan.tunnel.b_device))] = plan.tunnel
    base_labels = {frozenset((e.a, e.b)): e.label for e in base.edges}
    used = [l.network for l in plan.links] + ([plan.tunnel.network] if plan.tunnel else [])
    pool = (n for n in plan.wan_block.subnets(new_prefix=30) if not any(n.overlaps(u) for u in used))
    by_id = {d.id: d for d in topo.devices}

    for e in edges:
        if e.b == "SW-CORE" and e.kind == "trunk":  # normaliza: el núcleo siempre como origen
            e = Edge(e.b, e.a, e.label, e.kind)
        key = frozenset((e.a, e.b))
        label = base_labels.get(key, "")
        if e.kind == "trunk":
            other = by_id[e.b] if e.a == "SW-CORE" else by_id[e.a]
            if other.role == "access" and other.floor:
                seg = next(s for s in plan.floor_segments() if s.floor == other.floor)
                vlans = sorted([seg.vlan] + [s.vlan for s in plan.segments if s.role in ("voice", "cctv", "wifi", "mgmt")])
                label = "trunk " + ",".join(map(str, vlans))
            elif other.role == "server":
                label = f"trunk {plan.segment('servers').vlan},{plan.segment('mgmt').vlan}"
        elif key in known and not label:
            label = str(known[key].network)
        elif e.kind == "wan":
            try:
                net = next(pool)
            except StopIteration as exc:
                raise ValidationError(f"El bloque WAN {plan.wan_block} no tiene más /30 libres.") from exc
            # Lado A = el router de mayor jerarquía (edge > dist > router)
            rank = {"edge": 0, "dist": 1, "router": 2}
            a, b = sorted((e.a, e.b), key=lambda x: rank.get(by_id[x].role, 9))
            link = P2PLink(f"WAN-{a}-{b}", a, b, net)
            topo.extra_links.append(link)
            e = Edge(a, b, "", "wan")
            label = f"WAN {net}"
        topo.edges.append(replace(e, label=label or e.kind))


def extra_links_for(topo: Topology, device_id: str) -> list[tuple[P2PLink, str, str]]:
    """[(enlace, ip_local, vecino)] de los enlaces WAN cargados por el usuario para un equipo."""
    out = []
    for link in getattr(topo, "extra_links", []):
        if link.a_device == device_id:
            out.append((link, str(link.a_ip), link.b_device))
        elif link.b_device == device_id:
            out.append((link, str(link.b_ip), link.a_device))
    return out
