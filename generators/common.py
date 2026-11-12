"""
generators/common.py
====================
Utilidades compartidas por los 4 motores de plantillas CLI (Módulo 4).

Política de secretos: los generadores NUNCA escriben contraseñas reales.
Usan marcadores `<<ADMIN_SECRET>>`, `<<ENABLE_SECRET>>`, `<<VPN_PSK>>`,
`<<SNMPV3_AUTH>>`, `<<SNMPV3_PRIV>>` que se reemplazan en el despliegue
desde un gestor de secretos o desde el `.env` del operador (fuera del repo).
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from datetime import datetime

from core.ipam import AddressPlan, Segment
from core.state import ProjectConfig
from core.topology import PORTS_PER_ACCESS_SWITCH, Device, Topology, access_switches_for_floor

SECRET_PLACEHOLDERS = ("<<ADMIN_SECRET>>", "<<ENABLE_SECRET>>", "<<VPN_PSK>>",
                       "<<SNMPV3_AUTH>>", "<<SNMPV3_PRIV>>")

BLACKHOLE_VLAN = 999   # VLAN nativa / puertos sin uso
TRANSIT_VLAN = 900     # VLAN de tránsito (para switches L3 sin puerto enrutado)
LOCAL_AS = 65010       # ASN privado del CE (MPLS)
PROVIDER_AS = 65000    # ASN del PE del proveedor MPLS


@dataclass
class Extras:
    """Parámetros no secretos que dependen del sitio remoto / proveedor."""

    peer_public_ip: str = "<<PEER_PUBLIC_IP>>"
    remote_lan: str = "<<REMOTE_LAN_CIDR>>"
    dns_servers: tuple[str, ...] = ("1.1.1.1", "8.8.8.8")
    ntp_server: str = "pool.ntp.org"
    domain: str = "corp.local"

    @property
    def remote_lan_net(self) -> ipaddress.IPv4Network | None:
        try:
            return ipaddress.IPv4Network(self.remote_lan, strict=True)
        except ValueError:
            return None

    def remote_lan_parts(self) -> tuple[str, str, str]:
        """(red, máscara, wildcard) o marcadores si aún no se definió."""
        net = self.remote_lan_net
        if net is None:
            return "<<REMOTE_LAN>>", "<<REMOTE_MASK>>", "<<REMOTE_WILDCARD>>"
        return str(net.network_address), str(net.netmask), str(net.hostmask)


@dataclass
class GeneratedConfig:
    device_id: str
    hostname: str
    vendor: str
    role: str
    platform: str
    text: str

    @property
    def filename(self) -> str:
        return f"{self.vendor.lower()}_{self.hostname}.txt"

    @property
    def placeholders(self) -> list[str]:
        import re

        return sorted(set(re.findall(r"<<[A-Z0-9_]+>>", self.text)))


@dataclass
class Ctx:
    """Contexto que recibe cada plantilla."""

    cfg: ProjectConfig
    plan: AddressPlan
    topo: Topology
    extras: Extras = field(default_factory=Extras)

    # --- atajos ---------------------------------------------------------
    @property
    def service_segments(self) -> list[Segment]:
        return [s for s in self.plan.segments if s.role in ("voice", "cctv", "wifi", "mgmt")]

    @property
    def core_segments(self) -> list[Segment]:
        """Segmentos cuyo gateway vive en el SW-CORE (todo menos la DMZ)."""
        return [s for s in self.plan.segments if s.role != "dmz"]

    @property
    def dhcp_segments(self) -> list[Segment]:
        return [s for s in self.plan.segments if s.role in ("data", "voice", "wifi", "cctv")]

    def segment_for_floor(self, floor: int) -> Segment:
        for s in self.plan.floor_segments():
            if s.floor == floor:
                return s
        raise KeyError(floor)

    def trunk_vlans_for(self, device: Device) -> list[int]:
        if device.role == "server":
            return [self.plan.segment("servers").vlan, self.plan.segment("mgmt").vlan]
        seg = self.segment_for_floor(device.floor)
        return sorted([seg.vlan] + [s.vlan for s in self.service_segments])

    def all_trunk_vlans(self) -> list[int]:
        return sorted(s.vlan for s in self.core_segments)

    def access_index(self, device: Device) -> int:
        """Posición (1..n) del switch de acceso entre todos los downlinks del core."""
        downs = [d for d in self.topo.devices if d.role in ("access", "server")]
        return downs.index(device) + 1

    @property
    def mgmt_gateway(self) -> str:
        return str(self.plan.segment("mgmt").gateway)

    @property
    def mgmt_mask(self) -> str:
        return self.plan.segment("mgmt").mask

    @property
    def mgmt_prefix(self) -> int:
        return self.plan.segment("mgmt").prefix

    def router_id(self, device_id: str) -> str:
        return {"R-CORE": "1.1.1.1", "R-DIST": "2.2.2.2", "SW-CORE": "3.3.3.3"}[device_id]


# --------------------------------------------------------------------------- #
# Plan de puertos de un switch de acceso (independiente del fabricante)
# --------------------------------------------------------------------------- #


@dataclass
class PortGroup:
    kind: str    # user | camera | ap | server | unused
    start: int
    end: int
    vlan: int

    @property
    def count(self) -> int:
        return self.end - self.start + 1


def port_plan(ctx: Ctx, device: Device) -> list[PortGroup]:
    """Reparte usuarios, cámaras y AP del piso entre sus switches de 48 puertos."""
    total = PORTS_PER_ACCESS_SWITCH
    groups: list[PortGroup] = []
    if device.role == "server":
        seg = ctx.plan.segment("servers")
        groups.append(PortGroup("server", 1, 44, seg.vlan))
        groups.append(PortGroup("unused", 45, total, BLACKHOLE_VLAN))
        return groups

    seg = ctx.segment_for_floor(device.floor)
    floor_devices = [d for d in ctx.topo.by_role("access") if d.floor == device.floor]
    n_sw = len(floor_devices)  # los que existan en la topología (propuesta o cargada)
    idx = floor_devices.index(device)

    # Demanda total del piso, en orden de prioridad
    demand = [("user", seg.hosts_required, seg.vlan)]
    cctv, wifi, mgmt = ctx.plan.segment("cctv"), ctx.plan.segment("wifi"), ctx.plan.segment("mgmt")
    if cctv:
        demand.append(("camera", ctx.cfg.cameras_per_floor, cctv.vlan))
    if wifi:
        demand.append(("ap", ctx.cfg.ap_per_floor, mgmt.vlan))

    # Expandir a lista de puertos de todo el piso y tomar la porción de este switch
    flat: list[tuple[str, int]] = []
    for kind, qty, vlan in demand:
        flat.extend([(kind, vlan)] * qty)
    flat = flat[: n_sw * total]
    mine = flat[idx * total:(idx + 1) * total]

    port = 1
    i = 0
    while i < len(mine):
        kind, vlan = mine[i]
        j = i
        while j < len(mine) and mine[j] == (kind, vlan):
            j += 1
        groups.append(PortGroup(kind, port, port + (j - i) - 1, vlan))
        port += j - i
        i = j
    if port <= total:
        groups.append(PortGroup("unused", port, total, BLACKHOLE_VLAN))
    return groups


def header(ctx: Ctx, hostname: str, vendor: str, platform: str, comment: str = "!") -> str:
    c = comment
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"{c} ==================================================================",
        f"{c}  RED-LION-INTERCONNECTION · {ctx.cfg.project_name}",
        f"{c}  Equipo: {hostname}  ·  {vendor} {platform}",
        f"{c}  Generado: {now}  ·  Huella del diseño: {ctx.cfg.fingerprint()}",
        f"{c}  Reemplace los marcadores <<...>> desde el gestor de secretos ANTES",
        f"{c}  de aplicar. Nunca suba este archivo con secretos a un repositorio.",
        f"{c} ==================================================================",
    ]
    return "\n".join(lines)


def ranges(numbers: list[int]) -> str:
    """[20,30,40,99,101] → '20,30,40,99,101'; [1,2,3,5] → '1-3,5'."""
    numbers = sorted(set(numbers))
    out, start = [], None
    prev = None
    for n in numbers:
        if start is None:
            start = prev = n
        elif n == prev + 1:
            prev = n
        else:
            out.append(f"{start}-{prev}" if start != prev else str(start))
            start = prev = n
    if start is not None:
        out.append(f"{start}-{prev}" if start != prev else str(start))
    return ",".join(out)


def prefix_str(network) -> str:
    return f"{network.network_address}/{network.prefixlen}"


# --------------------------------------------------------------------------- #
# Enlaces WAN cargados por el usuario (Módulo 3 → carga de topología)
# --------------------------------------------------------------------------- #


def extra_wan_lines(vendor: str, ctx: Ctx, device: Device) -> list[str]:
    """Interfaces /30 + OSPF para los enlaces WAN que el usuario agregó a la topología."""
    from core.topology_io import extra_links_for

    links = extra_links_for(ctx.topo, device.id)
    if not links:
        return []
    L: list[str] = []
    for i, (link, ip, peer) in enumerate(links):
        net, mask, wild = link.network.network_address, link.mask, link.wildcard
        if vendor == "Cisco":
            L += [f"interface GigabitEthernet0/1/{i + 1}", f" description WAN-{peer}",
                  f" ip address {ip} {mask}", " ip ospf network point-to-point", " no shutdown", "!",
                  "router ospf 1", f" network {net} {wild} area 0", "!"]
        elif vendor == "Huawei":
            L += [f"interface GigabitEthernet0/0/{4 + i}", f" description WAN-{peer}",
                  f" ip address {ip} {mask}", " ospf network-type p2p", "#",
                  "ospf 1", " area 0.0.0.0", f"  network {net} {wild}", "#"]
        elif vendor == "Fortinet":
            L += ["config system interface", f'    edit "port{5 + i}"', f'        set alias "WAN-{peer}"',
                  f"        set ip {ip} {mask}", "        set allowaccess ping", "        set role wan",
                  "    next", "end",
                  "config router ospf", "    config network", f"        edit {50 + i}",
                  f"            set prefix {net} {mask}", "        next", "    end", "end"]
        else:  # MikroTik
            L += [f"/interface ethernet set [find default-name=ether{6 + i}] comment=WAN-{peer}",
                  f"/ip address add address={ip}/30 interface=ether{6 + i} comment=WAN-{peer}",
                  f"/routing ospf interface-template add area=backbone-v2 networks={net}/30"]
    return L


def device_summary(ctx: Ctx, device: Device) -> tuple[list[int], list[tuple[str, str]]]:
    """(VLAN, [(interfaz, IP/prefijo)]) del equipo, tomados del plan: lo que su configuración aplica."""
    from core.topology_io import extra_links_for

    p, role = ctx.plan, device.role
    vlans: list[int] = []
    ips: list[tuple[str, str]] = []
    if role == "edge":
        isp, down, dmz = p.link("ISP-EDGE"), p.link("EDGE-DIST"), p.segment("dmz")
        ips += [("WAN-ISP", f"{isp.b_ip}/30"), ("P2P-R-DIST", f"{down.a_ip}/30")]
        if dmz:
            vlans.append(dmz.vlan)
            ips.append((f"DMZ (VLAN {dmz.vlan})", f"{dmz.gateway}/{dmz.prefix}"))
        if p.tunnel:
            ips.append((p.tunnel.name, f"{p.tunnel.a_ip}/30"))
    elif role == "dist":
        up, down = p.link("EDGE-DIST"), p.link("DIST-CORESW")
        ips += [("P2P-R-CORE", f"{up.b_ip}/30"), ("P2P-SW-CORE", f"{down.a_ip}/30")]
    elif role == "core":
        up = p.link("DIST-CORESW")
        ips.append(("P2P-R-DIST", f"{up.b_ip}/30"))
        for s in ctx.core_segments:
            vlans.append(s.vlan)
            ips.append((f"Vlan{s.vlan} {s.tag}", f"{s.gateway}/{s.prefix}"))
    elif role in ("access", "server"):
        mgmt = p.segment("mgmt")
        vlans = ctx.trunk_vlans_for(device)
        ips.append((f"Vlan{mgmt.vlan} GESTION", f"{device.mgmt_ip}/{mgmt.prefix}"))
    for link, ip, peer in extra_links_for(ctx.topo, device.id):
        ips.append((f"WAN-{peer}", f"{ip}/30"))
    return sorted(vlans), ips
