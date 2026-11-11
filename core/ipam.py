"""
core/ipam.py
============
Módulo 2 — Planificación IP matemática estricta (IPv4 / IPv6).

Todo se calcula con la librería estándar `ipaddress`; no hay direcciones
"inventadas". Reglas aplicadas:

* VLSM: los segmentos se ordenan de mayor a menor y se asignan contiguos,
  alineados a su frontera natural, desde la red base. Esto minimiza el
  desperdicio y permite sumarizar.
* Tamaño de cada segmento = hosts requeridos × (1 + crecimiento) + red + broadcast,
  redondeado a la siguiente potencia de 2.
* Gateway = primera IP utilizable (convención Cisco Packet Tracer).
* Enlaces WAN punto a punto: /30 estrictos (4 direcciones, 2 utilizables),
  tomados de un bloque dedicado para no fragmentar el espacio LAN.
* IPv6: cada VLAN recibe un /64 cuyo ID de subred es el número de VLAN
  (ej. VLAN 101 → 2001:db8:acad:101::/64). Los enlaces P2P usan /127 (RFC 6164)
  tomados de los últimos /64 del bloque.
"""

from __future__ import annotations

import ipaddress
import math
from dataclasses import dataclass, field

from .state import ProjectConfig
from .validators import ValidationError

IPv4Net = ipaddress.IPv4Network
IPv6Net = ipaddress.IPv6Network

MIN_LAN_PREFIX = 29  # ningún segmento de usuario más pequeño que /29

# Numeración de VLAN corporativa (documentada en docs/arquitectura.md)
VLAN_FLOOR_BASE = 100   # Piso n → VLAN 100+n
VLAN_VOICE = 20
VLAN_CCTV = 30
VLAN_WIFI = 40
VLAN_SERVERS = 50
VLAN_DMZ = 60
VLAN_MGMT = 99


# --------------------------------------------------------------------------- #
# Modelos de datos
# --------------------------------------------------------------------------- #


@dataclass
class Segment:
    name: str
    vlan: int
    role: str             # data | voice | cctv | wifi | servers | dmz | mgmt
    floor: int | None
    hosts_required: int
    network: IPv4Net | None = None
    ipv6: IPv6Net | None = None

    # ---- propiedades derivadas (todas calculadas con ipaddress) ----
    @property
    def prefix(self) -> int:
        return self.network.prefixlen

    @property
    def mask(self) -> str:
        return str(self.network.netmask)

    @property
    def wildcard(self) -> str:
        return str(self.network.hostmask)

    @property
    def usable(self) -> int:
        return self.network.num_addresses - 2

    @property
    def gateway(self) -> ipaddress.IPv4Address:
        return self.network.network_address + 1

    @property
    def first_host(self) -> ipaddress.IPv4Address:
        return self.network.network_address + 1

    @property
    def last_host(self) -> ipaddress.IPv4Address:
        return self.network.broadcast_address - 1

    @property
    def broadcast(self) -> ipaddress.IPv4Address:
        return self.network.broadcast_address

    @property
    def reserved_static(self) -> int:
        """IPs reservadas al inicio para gateway, SVIs, impresoras, AP, etc."""
        return max(2, min(10, self.usable // 6))

    @property
    def dhcp_start(self) -> ipaddress.IPv4Address:
        return self.network.network_address + 1 + self.reserved_static

    @property
    def dhcp_end(self) -> ipaddress.IPv4Address:
        return self.last_host

    @property
    def utilization(self) -> float:
        return round(100 * self.hosts_required / self.usable, 1) if self.usable else 0.0

    @property
    def ipv6_gateway(self) -> ipaddress.IPv6Address:
        return self.ipv6.network_address + 1

    @property
    def tag(self) -> str:
        """Nombre corto apto para CLI (sin espacios)."""
        return self.name.upper().replace(" ", "_").replace("/", "_")


@dataclass
class P2PLink:
    name: str
    a_device: str
    b_device: str
    network: IPv4Net
    ipv6: IPv6Net | None = None
    provider_managed: bool = False

    @property
    def a_ip(self) -> ipaddress.IPv4Address:  # lado "upstream" = 1.ª utilizable
        return self.network.network_address + 1

    @property
    def b_ip(self) -> ipaddress.IPv4Address:  # lado "downstream" = 2.ª utilizable
        return self.network.network_address + 2

    @property
    def mask(self) -> str:
        return str(self.network.netmask)

    @property
    def wildcard(self) -> str:
        return str(self.network.hostmask)

    @property
    def broadcast(self) -> ipaddress.IPv4Address:
        return self.network.broadcast_address

    @property
    def a_ip6(self) -> ipaddress.IPv6Address | None:
        return self.ipv6.network_address if self.ipv6 else None

    @property
    def b_ip6(self) -> ipaddress.IPv6Address | None:
        return self.ipv6.network_address + 1 if self.ipv6 else None


@dataclass
class AddressPlan:
    base_v4: IPv4Net
    base_v6: IPv6Net
    wan_block: IPv4Net
    segments: list[Segment] = field(default_factory=list)
    links: list[P2PLink] = field(default_factory=list)
    tunnel: P2PLink | None = None

    # ------------------------------------------------------------------ #
    @property
    def allocated_addresses(self) -> int:
        return sum(s.network.num_addresses for s in self.segments)

    @property
    def required_hosts(self) -> int:
        return sum(s.hosts_required for s in self.segments)

    @property
    def usable_allocated(self) -> int:
        return sum(s.usable for s in self.segments)

    @property
    def efficiency(self) -> float:
        """% de IPs utilizables asignadas que realmente se necesitan."""
        return round(100 * self.required_hosts / self.usable_allocated, 1) if self.segments else 0.0

    @property
    def base_usage(self) -> float:
        return round(100 * self.allocated_addresses / self.base_v4.num_addresses, 2)

    @property
    def summary_route(self) -> IPv4Net:
        """Ruta sumarizada mínima que cubre todos los segmentos LAN."""
        nets = [s.network for s in self.segments]
        first, last = min(n.network_address for n in nets), max(n.broadcast_address for n in nets)
        summary = IPv4Net(f"{first}/32")
        while not (summary.network_address <= first and summary.broadcast_address >= last):
            summary = summary.supernet()
        return summary

    def by_role(self, role: str) -> list[Segment]:
        return [s for s in self.segments if s.role == role]

    def segment(self, role: str) -> Segment | None:
        found = self.by_role(role)
        return found[0] if found else None

    def link(self, name: str) -> P2PLink:
        for link in self.links:
            if link.name == name:
                return link
        raise KeyError(name)

    def floor_segments(self) -> list[Segment]:
        return sorted(self.by_role("data"), key=lambda s: s.floor or 0)


# --------------------------------------------------------------------------- #
# Matemática de subnetting
# --------------------------------------------------------------------------- #


def prefix_for_hosts(hosts: int, min_prefix_len: int = MIN_LAN_PREFIX) -> int:
    """Menor subred IPv4 que aloja `hosts` utilizables (+ red + broadcast)."""
    if hosts < 1:
        raise ValidationError("Un segmento necesita al menos 1 host.")
    bits = math.ceil(math.log2(hosts + 2))
    return min(32 - bits, min_prefix_len)


def with_growth(hosts: int, growth_pct: int) -> int:
    return math.ceil(hosts * (1 + growth_pct / 100))


def vlsm_allocate(base: IPv4Net, requests: list[tuple[Segment, int]]) -> None:
    """Asigna subredes contiguas, de mayor a menor, alineadas a su frontera.

    `requests` = [(segmento, prefijo)]. Modifica `segmento.network` in situ.
    """
    cursor = int(base.network_address)
    end = int(base.broadcast_address)
    for seg, prefix in sorted(requests, key=lambda r: (r[1], r[0].vlan)):
        size = 2 ** (32 - prefix)
        if cursor % size:  # alinear a la frontera natural del bloque
            cursor += size - (cursor % size)
        if cursor + size - 1 > end:
            raise ValidationError(
                f"La red base {base} no alcanza: falta espacio para '{seg.name}' (/{prefix}). "
                "Use un prefijo base más corto (p. ej. /16) o reduzca hosts/crecimiento."
            )
        seg.network = IPv4Net(f"{ipaddress.IPv4Address(cursor)}/{prefix}")
        cursor += size


def ipv6_for_vlan(base: IPv6Net, vlan: int) -> IPv6Net:
    """/64 cuyo identificador de subred es el número de VLAN en notación hex-decimal legible."""
    available = 2 ** (64 - base.prefixlen)
    # Con un /48 (o mayor) se usa el número de VLAN "leído" como hex
    # (101 → 0x101) para que la dirección sea legible: 2001:db8:acad:101::/64.
    # Con bloques más pequeños (/49–/56) se usa el valor decimal de la VLAN.
    subnet_id = int(str(vlan), 16) if base.prefixlen <= 48 else vlan
    if subnet_id >= available - 8:  # los últimos /64 se reservan para P2P

        raise ValidationError(f"El bloque IPv6 {base} no tiene /64 suficientes para VLAN {vlan}.")
    return IPv6Net((int(base.network_address) + (subnet_id << 64), 64))


def ipv6_p2p(base: IPv6Net, index: int) -> IPv6Net:
    """/127 dentro de uno de los últimos /64 del bloque (reservados para infraestructura)."""
    available = 2 ** (64 - base.prefixlen)
    subnet_id = available - 1 - index
    container = int(base.network_address) + (subnet_id << 64)
    return IPv6Net((container, 127))


# --------------------------------------------------------------------------- #
# Constructor del plan
# --------------------------------------------------------------------------- #


def build_address_plan(cfg: ProjectConfig) -> AddressPlan:
    errors = cfg.validate()
    if errors:
        raise ValidationError(" | ".join(errors))

    base_v4 = IPv4Net(cfg.ipv4_base)
    base_v6 = IPv6Net(cfg.ipv6_base)
    wan_block = IPv4Net(cfg.wan_block)
    if base_v4.overlaps(wan_block):
        raise ValidationError("El bloque WAN /30 no puede solaparse con la red base LAN.")

    plan = AddressPlan(base_v4=base_v4, base_v6=base_v6, wan_block=wan_block)
    requests: list[tuple[Segment, int]] = []

    # 1) Datos por piso/zona -------------------------------------------------
    per_floor = math.ceil(cfg.hosts_total / cfg.floors)
    floor_hosts = with_growth(per_floor, cfg.growth_pct)
    for f in range(1, cfg.floors + 1):
        seg = Segment(f"Piso {f:02d} Datos", VLAN_FLOOR_BASE + f, "data", f, floor_hosts)
        requests.append((seg, prefix_for_hosts(floor_hosts)))

    # 2) Servicios transversales --------------------------------------------
    if cfg.has("VoIP"):
        h = with_growth(cfg.hosts_total, cfg.growth_pct)
        requests.append((Segment("Voz IP", VLAN_VOICE, "voice", None, h), prefix_for_hosts(h)))
    if cfg.has("CCTV") and cfg.cameras_per_floor:
        h = with_growth(cfg.cameras_per_floor * cfg.floors + 2, cfg.growth_pct)  # +2 NVR
        requests.append((Segment("CCTV", VLAN_CCTV, "cctv", None, h), prefix_for_hosts(h)))
    if cfg.has("Wi-Fi"):
        h = with_growth(math.ceil(cfg.hosts_total * 0.6), cfg.growth_pct)  # 60 % BYOD
        requests.append((Segment("WiFi Clientes", VLAN_WIFI, "wifi", None, h), prefix_for_hosts(h)))
    if cfg.has("Servidores/DMZ"):
        requests.append((Segment("Servidores", VLAN_SERVERS, "servers", None, 24), prefix_for_hosts(24)))
        requests.append((Segment("DMZ", VLAN_DMZ, "dmz", None, 10), prefix_for_hosts(10)))

    # 3) Gestión: 1 IP por equipo de red + AP + margen
    access_sw = cfg.floors * max(1, math.ceil((floor_hosts + cfg.cameras_per_floor + cfg.ap_per_floor) / 48))
    mgmt_hosts = access_sw + 6 + (cfg.ap_per_floor * cfg.floors if cfg.has("Wi-Fi") else 0) + 10
    requests.append((Segment("Gestion", VLAN_MGMT, "mgmt", None, mgmt_hosts), prefix_for_hosts(mgmt_hosts)))

    vlsm_allocate(base_v4, requests)
    plan.segments = sorted((s for s, _ in requests), key=lambda s: s.vlan)

    for seg in plan.segments:
        seg.ipv6 = ipv6_for_vlan(base_v6, seg.vlan)

    # 4) Enlaces WAN punto a punto /30 --------------------------------------
    p2p_pool = wan_block.subnets(new_prefix=30)
    isp = IPv4Net(cfg.isp_ipv4_link)
    plan.links.append(P2PLink("ISP-EDGE", "ISP", "R-CORE", isp, ipv6_p2p(base_v6, 0), provider_managed=True))
    plan.links.append(P2PLink("EDGE-DIST", "R-CORE", "R-DIST", next(p2p_pool), ipv6_p2p(base_v6, 1)))
    plan.links.append(P2PLink("DIST-CORESW", "R-DIST", "SW-CORE", next(p2p_pool), ipv6_p2p(base_v6, 2)))
    if cfg.vpn_type in ("IPsec", "MPLS"):
        name = "VPN-TUNNEL" if cfg.vpn_type == "IPsec" else "MPLS-CE-PE"
        plan.tunnel = P2PLink(name, "R-CORE", "REMOTO", next(p2p_pool), ipv6_p2p(base_v6, 3))
    return plan


def plan_to_rows(plan: AddressPlan) -> list[dict]:
    """Tabla plana para st.dataframe / exportación CSV."""
    rows = []
    for s in plan.segments:
        rows.append({
            "VLAN": s.vlan,
            "Segmento": s.name,
            "Hosts req.": s.hosts_required,
            "Red": str(s.network.network_address),
            "Prefijo": f"/{s.prefix}",
            "Máscara": s.mask,
            "Gateway": str(s.gateway),
            "Rango útil": f"{s.first_host} – {s.last_host}",
            "Broadcast": str(s.broadcast),
            "Utilizables": s.usable,
            "Uso %": s.utilization,
            "IPv6 /64": str(s.ipv6),
            "GW IPv6": str(s.ipv6_gateway),
        })
    return rows


def links_to_rows(plan: AddressPlan) -> list[dict]:
    links = list(plan.links) + ([plan.tunnel] if plan.tunnel else [])
    return [{
        "Enlace": l.name,
        "Extremo A": l.a_device,
        "IP A": str(l.a_ip),
        "Extremo B": l.b_device,
        "IP B": str(l.b_ip),
        "Red /30": str(l.network),
        "Máscara": l.mask,
        "Broadcast": str(l.broadcast),
        "IPv6 /127": str(l.ipv6) if l.ipv6 else "—",
    } for l in links]
