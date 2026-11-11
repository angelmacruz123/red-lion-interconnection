"""
core/topology.py
================
Módulo 3 — Topología y modelado estructural.

Construye un grafo jerárquico (modelo de 3 capas + borde) SOLO a partir del
plan IP calculado. Cada nodo y cada arista llevan la IP/VLAN real del plan,
por eso el diagrama nunca muestra datos inventados.

    Cloud ISP ─/30─ R-CORE (borde) ─/30─ R-DIST ─/30─ SW-CORE (L3)
                       │                                 ├─ SW-ACC-P01..Pnn (trunk)
                       └─ DMZ                            └─ SW-SRV (granja de servidores)

Exporta a Graphviz DOT (st.graphviz_chart) y a Mermaid (interactivo).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .ipam import AddressPlan
from .state import ProjectConfig

PORTS_PER_ACCESS_SWITCH = 48


@dataclass
class Device:
    id: str
    hostname: str
    role: str        # isp | edge | dist | core | access | server | dmz | remote
    layer: str       # Borde | Distribución | Núcleo | Acceso | Servicios
    mgmt_ip: str = ""
    floor: int | None = None
    details: list[str] = field(default_factory=list)


@dataclass
class Edge:
    a: str
    b: str
    label: str
    kind: str = "p2p"  # p2p | trunk | vpn


@dataclass
class Topology:
    devices: list[Device] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)

    def get(self, device_id: str) -> Device:
        for d in self.devices:
            if d.id == device_id:
                return d
        raise KeyError(device_id)

    def by_role(self, role: str) -> list[Device]:
        return [d for d in self.devices if d.role == role]

    @property
    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for d in self.devices:
            out[d.role] = out.get(d.role, 0) + 1
        return out


# --------------------------------------------------------------------------- #


def access_switches_for_floor(cfg: ProjectConfig, hosts_floor: int) -> int:
    """Switches de 48 puertos necesarios en un piso (PC + cámaras + AP)."""
    ports = hosts_floor
    if cfg.has("CCTV"):
        ports += cfg.cameras_per_floor
    if cfg.has("Wi-Fi"):
        ports += cfg.ap_per_floor
    return max(1, math.ceil(ports / PORTS_PER_ACCESS_SWITCH))


def build_topology(cfg: ProjectConfig, plan: AddressPlan) -> Topology:
    topo = Topology()
    pre = cfg.hostname_prefix
    mgmt = plan.segment("mgmt")
    # IPs de gestión: se toman en orden desde la 2.ª IP útil de la VLAN 99
    mgmt_hosts = mgmt.network.hosts()
    next(mgmt_hosts)  # .1 = gateway de gestión (SVI en SW-CORE)

    def mgmt_ip() -> str:
        return str(next(mgmt_hosts))

    isp_link = plan.link("ISP-EDGE")
    edge_dist = plan.link("EDGE-DIST")
    dist_core = plan.link("DIST-CORESW")

    topo.devices.append(Device("ISP", "ISP-CLOUD", "isp", "Borde",
                               details=[f"GW {isp_link.a_ip}", f"{cfg.isp_bandwidth_mbps} Mbps"]))
    topo.devices.append(Device("R-CORE", f"{pre}-R-CORE", "edge", "Borde", mgmt_ip(),
                               details=[f"WAN {isp_link.b_ip}/30", "NAT · ACL · VPN"]))
    topo.devices.append(Device("R-DIST", f"{pre}-R-DIST", "dist", "Distribución", mgmt_ip(),
                               details=[f"{edge_dist.b_ip}/30", f"{dist_core.a_ip}/30", "OSPF área 0"]))
    topo.devices.append(Device("SW-CORE", f"{pre}-SW-CORE", "core", "Núcleo", mgmt_ip(),
                               details=[f"{dist_core.b_ip}/30", f"{len(plan.segments)} SVIs", "DHCP"]))

    topo.edges.append(Edge("ISP", "R-CORE", f"{isp_link.network}"))
    topo.edges.append(Edge("R-CORE", "R-DIST", f"{edge_dist.network}"))
    topo.edges.append(Edge("R-DIST", "SW-CORE", f"{dist_core.network}"))

    # Acceso por piso -------------------------------------------------------
    for seg in plan.floor_segments():
        n_sw = access_switches_for_floor(cfg, seg.hosts_required)
        for idx in range(1, n_sw + 1):
            suffix = f"P{seg.floor:02d}" + (f"-{idx}" if n_sw > 1 else "")
            dev = Device(f"SW-ACC-{suffix}", f"{pre}-SW-ACC-{suffix}", "access", "Acceso",
                         mgmt_ip(), floor=seg.floor,
                         details=[f"VLAN {seg.vlan} · {seg.network}"])
            topo.devices.append(dev)
            vlans = sorted([seg.vlan] + [s.vlan for s in plan.segments
                                         if s.role in ("voice", "cctv", "wifi", "mgmt")])
            topo.edges.append(Edge("SW-CORE", dev.id, "trunk " + ",".join(map(str, vlans)), "trunk"))

    # Servicios -------------------------------------------------------------
    servers = plan.segment("servers")
    if servers:
        topo.devices.append(Device("SW-SRV", f"{pre}-SW-SRV", "server", "Servicios", mgmt_ip(),
                                   details=[f"VLAN {servers.vlan} · {servers.network}"]))
        topo.edges.append(Edge("SW-CORE", "SW-SRV", f"trunk {servers.vlan},{mgmt.vlan}", "trunk"))
    dmz = plan.segment("dmz")
    if dmz:
        topo.devices.append(Device("DMZ", f"{pre}-DMZ", "dmz", "Servicios",
                                   details=[f"VLAN {dmz.vlan} · {dmz.network}", "Web · Correo · DNS"]))
        topo.edges.append(Edge("R-CORE", "DMZ", f"{dmz.network}"))
    if plan.tunnel:
        topo.devices.append(Device("REMOTO", "SEDE-REMOTA", "remote", "Borde",
                                   details=[f"{cfg.vpn_type} · {plan.tunnel.b_ip}/30"]))
        topo.edges.append(Edge("R-CORE", "REMOTO", f"{cfg.vpn_type} {plan.tunnel.network}", "vpn"))
    elif cfg.vpn_type == "SSL":
        topo.devices.append(Device("REMOTO", "USUARIOS-REMOTOS", "remote", "Borde",
                                   details=["SSL VPN · TLS 443"]))
        topo.edges.append(Edge("R-CORE", "REMOTO", "SSL VPN", "vpn"))
    return topo


# --------------------------------------------------------------------------- #
# Exportadores
# --------------------------------------------------------------------------- #

_PALETTE = {
    "isp": ("#1c1214", "#9c8a8d"),
    "edge": ("#7f0d16", "#ff4d5e"),
    "dist": ("#5c0a12", "#ef233c"),
    "core": ("#3d0a10", "#ff6b78"),
    "access": ("#1a1012", "#b8a6a8"),
    "server": ("#3a1f08", "#f59e0b"),
    "dmz": ("#2b0f2a", "#e879f9"),
    "remote": ("#1c1214", "#d6c8ca"),
}


def _dot_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def grouped_view(topo: Topology) -> tuple[list[Device], list[Edge]]:
    """Vista para diagramas: agrupa los switches de acceso de cada piso en un solo nodo.

    No inventa nada: cada nodo agrupado lista los hostnames e IP de gestión reales
    de sus switches. Así un edificio de 15+ pisos sigue siendo legible.
    """
    nodes: list[Device] = []
    edges: list[Edge] = []
    floors: dict[int, list[Device]] = {}
    for d in topo.devices:
        if d.role == "access":
            floors.setdefault(d.floor, []).append(d)
        else:
            nodes.append(d)
    for floor, devs in sorted(floors.items()):
        lines = [f"{x.id.replace('SW-ACC-', '')} · {x.mgmt_ip}" for x in devs] + devs[0].details
        nodes.append(Device(f"PISO-{floor:02d}", f"PISO {floor:02d} · {len(devs)} SW", "access",
                            "Acceso", floor=floor, details=lines))
    seen = set()
    for e in topo.edges:
        b = e.b
        if e.b.startswith("SW-ACC-"):
            b = f"PISO-{topo.get(e.b).floor:02d}"
            if b in seen:
                continue
            seen.add(b)
        edges.append(Edge(e.a, b, e.label, e.kind))
    return nodes, edges


def to_dot(topo: Topology, title: str = "") -> str:
    lines = [
        "digraph G {",
        '  graph [rankdir=LR, bgcolor="transparent", nodesep=0.18, ranksep=0.9, '
        f'fontname="Inter", fontcolor="#f4eeee", label="{_dot_escape(title)}", labelloc=t, fontsize=14];',
        '  node [shape=box, style="rounded,filled", fontname="Inter", fontsize=10, penwidth=1.2];',
        '  edge [fontname="JetBrains Mono", fontsize=8, color="#4a2a2e", fontcolor="#b8a6a8", arrowhead=none];',
    ]
    nodes, edges = grouped_view(topo)
    for d in nodes:
        fill, stroke = _PALETTE.get(d.role, ("#18181b", "#e4e4e7"))
        shape = "ellipse" if d.role in ("isp", "remote") else "box"
        sub = "\\n".join(_dot_escape(x) for x in ([d.mgmt_ip] if d.mgmt_ip else []) + d.details)
        label = f"{_dot_escape(d.hostname)}" + (f"\\n{sub}" if sub else "")
        lines.append(f'  "{d.id}" [label="{label}", shape={shape}, fillcolor="{fill}", '
                     f'color="{stroke}", fontcolor="#fafafa"];')

    # Ranking por capa para que el árbol sea realmente jerárquico
    ranks = {
        "Acc": [d.id for d in nodes if d.role in ("access", "server")],
    }
    for ids in ranks.values():
        if ids:
            lines.append("  { rank=same; " + " ".join(f'"{i}";' for i in ids) + " }")

    for e in edges:
        style = {"p2p": 'color="#ef233c", penwidth=1.8',
                 "trunk": 'color="#4a2a2e"',
                 "vpn": 'color="#fbbf24", style=dashed, penwidth=1.4'}[e.kind]
        lines.append(f'  "{e.a}" -> "{e.b}" [label="{_dot_escape(e.label)}", {style}];')
    lines.append("}")
    return "\n".join(lines)


def to_mermaid(topo: Topology) -> str:
    def mid(x: str) -> str:
        return x.replace("-", "_")

    nodes, edges = grouped_view(topo)
    out = ["flowchart LR"]
    for d in nodes:
        text = d.hostname + (f"<br/>{d.mgmt_ip}" if d.mgmt_ip else "") + "".join(f"<br/>{x}" for x in d.details[:3])
        text = text.replace('"', "'")
        if d.role in ("isp", "remote"):
            out.append(f'  {mid(d.id)}(("{text}"))')
        else:
            out.append(f'  {mid(d.id)}["{text}"]')
    for e in edges:
        arrow = "-.->" if e.kind == "vpn" else "---"
        out.append(f'  {mid(e.a)} {arrow}|"{e.label}"| {mid(e.b)}')
    classes = {
        "isp": "fill:#1c1214,stroke:#9c8a8d,color:#fff",
        "edge": "fill:#7f0d16,stroke:#ff4d5e,color:#fff",
        "dist": "fill:#5c0a12,stroke:#ef233c,color:#fff",
        "core": "fill:#3d0a10,stroke:#ff6b78,color:#fff",
        "access": "fill:#1a1012,stroke:#b8a6a8,color:#fff",
        "server": "fill:#3a1f08,stroke:#f59e0b,color:#fff",
        "dmz": "fill:#2b0f2a,stroke:#e879f9,color:#fff",
        "remote": "fill:#1c1214,stroke:#d6c8ca,color:#fff",
    }
    for role, style in classes.items():
        ids = [mid(d.id) for d in nodes if d.role == role]
        if ids:
            out.append(f"  classDef {role} {style}")
            out.append(f"  class {','.join(ids)} {role}")
    return "\n".join(out)
