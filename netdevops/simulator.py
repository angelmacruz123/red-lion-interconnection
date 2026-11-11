"""
netdevops/simulator.py
======================
Simulación controlada de equipos para practicar sin hardware.

No hay respuestas inventadas al azar: el simulador responde a partir del plan
IP, la topología y la configuración que la propia herramienta generó. Si el
diseño cambia en el Módulo 1, las salidas simuladas cambian igual.

Cada equipo simulado tiene un estado (`SimState`): arranca "de fábrica"
(sin nombre, sin VLAN, sin IP, puertos apagados) y cambia a medida que el
despliegue guiado le aplica categorías. Así se puede demostrar el flujo
completo conectar → configurar → verificar sin hardware.
"""

from __future__ import annotations

import ipaddress
import re
import time
from dataclasses import dataclass, field

from core.ipam import AddressPlan
from core.topology import Device, Topology
from core.validators import redact_secrets, validate_command

from .ssh_client import CommandResult, validate_config_line

ALL_CATEGORIES = ("hostname", "vlans", "ip", "ports", "routing", "dhcp", "seguridad", "servicios")

_HOSTNAME_RX = [
    re.compile(r"^hostname\s+(\S+)"),                    # Cisco
    re.compile(r"^sysname\s+(\S+)"),                     # Huawei
    re.compile(r'^\s*set hostname\s+"?([^"\s]+)"?'),       # Fortinet
    re.compile(r"^/system identity set name=(\S+)"),      # MikroTik
]


def factory_hostname(vendor: str, role: str) -> str:
    switch = role in ("core", "access", "server")
    return {"Cisco": "Switch" if switch else "Router", "Huawei": "HUAWEI",
            "Fortinet": "FortiSwitch" if switch else "FortiGate", "MikroTik": "MikroTik"}[vendor]


@dataclass
class SimState:
    hostname: str
    applied: set[str] = field(default_factory=set)
    config_lines: list[str] = field(default_factory=list)
    in_config: bool = False

    @classmethod
    def factory(cls, vendor: str, device: Device) -> "SimState":
        return cls(factory_hostname(vendor, device.role))

    @classmethod
    def deployed(cls, device: Device) -> "SimState":
        return cls(device.hostname, set(ALL_CATEGORIES))

    def mark(self, categories) -> None:
        self.applied.update(categories)


class LabSimulator:
    def __init__(self, plan: AddressPlan, topo: Topology, device: Device, vendor: str, config_text: str,
                 state: SimState | None = None):
        self.plan, self.topo, self.dev, self.vendor = plan, topo, device, vendor
        self.config_text = config_text
        self.state = state or SimState.deployed(device)

    def has(self, category: str) -> bool:
        return category in self.state.applied

    def on_block_applied(self, category: str) -> None:
        self.state.applied.add(category)

    # ------------------------------------------------------------------ #
    # Recepción de configuración (despliegue guiado)
    # ------------------------------------------------------------------ #
    def send_lines(self, lines: list[str]) -> str:
        out = []
        for line in lines:
            validate_config_line(line)
            s = line.strip()
            for rx in _HOSTNAME_RX:
                m = rx.search(s)
                if m:
                    self.state.hostname = m.group(1)
            if s in ("configure terminal", "system-view"):
                self.state.in_config = True
            elif s in ("end", "return"):
                self.state.in_config = False
            elif s in ("write memory", "save"):
                out.append(f"{self.prompt()} {s}\n" + ("Building configuration...\n[OK]" if s == "write memory"
                                                       else "The current configuration will be written to the device.\n"
                                                            "Are you sure to continue?[Y/N]:y\nSave the configuration successfully."))
                continue
            else:
                self.state.config_lines.append(line)
            out.append(f"{self.prompt()} {s}")
            time.sleep(0.002)
        return "\n".join(out)

    # ------------------------------------------------------------------ #
    # Modelo de interfaces y rutas del equipo simulado
    # ------------------------------------------------------------------ #
    def interfaces(self) -> list[tuple[str, str, int, str]]:
        """(nombre, ip, prefijo, descripción)"""
        p, role = self.plan, self.dev.role
        names = {
            "Cisco": ("GigabitEthernet0/0/0", "GigabitEthernet0/0/1", "GigabitEthernet0/0/2", "Vlan"),
            "Huawei": ("GigabitEthernet0/0/0", "GigabitEthernet0/0/1", "GigabitEthernet0/0/2", "Vlanif"),
            "Fortinet": ("wan1", "port2", "dmz", "vlan"),
            "MikroTik": ("ether1", "ether2", "ether3", "vlan"),
        }[self.vendor]
        out = []
        if role == "edge":
            isp, down = p.link("ISP-EDGE"), p.link("EDGE-DIST")
            out.append((names[0], str(isp.b_ip), 30, "WAN-ISP"))
            out.append((names[1], str(down.a_ip), 30, "P2P-R-DIST"))
            if p.segment("dmz"):
                d = p.segment("dmz")
                out.append((names[2], str(d.gateway), d.prefix, "DMZ"))
            if p.tunnel and self.has("servicios"):
                out.append(("Tunnel0", str(p.tunnel.a_ip), 30, p.tunnel.name))
        elif role == "dist":
            up, down = p.link("EDGE-DIST"), p.link("DIST-CORESW")
            out.append((names[0], str(up.b_ip), 30, "P2P-R-CORE"))
            out.append((names[1], str(down.a_ip), 30, "P2P-SW-CORE"))
        elif role == "core":
            up = p.link("DIST-CORESW")
            out.append(("Uplink", str(up.b_ip), 30, "P2P-R-DIST"))
            for s in p.segments:
                if s.role != "dmz":
                    out.append((f"{names[3]}{s.vlan}", str(s.gateway), s.prefix, s.tag))
        else:
            m = p.segment("mgmt")
            out.append((f"{names[3]}{m.vlan}", self.dev.mgmt_ip, m.prefix, "GESTION"))
        return out

    def routes(self) -> list[tuple[str, str, str]]:
        """(código, destino, siguiente salto)"""
        p, role = self.plan, self.dev.role
        rows = [("C", f"{ipaddress.ip_interface(f'{ip}/{pl}').network}", f"directa {n}")
                for n, ip, pl, _ in self.interfaces()]
        summ = str(p.summary_route)
        if role == "edge":
            rows.insert(0, ("S*", "0.0.0.0/0", str(p.link("ISP-EDGE").a_ip)))
            rows.append(("O", summ, str(p.link("EDGE-DIST").b_ip)))
        elif role == "dist":
            rows.insert(0, ("O*E2", "0.0.0.0/0", str(p.link("EDGE-DIST").a_ip)))
            rows.append(("O", summ, str(p.link("DIST-CORESW").b_ip)))
        elif role == "core":
            rows.insert(0, ("O*E2", "0.0.0.0/0", str(p.link("DIST-CORESW").a_ip)))
            rows.append(("O", str(p.link("EDGE-DIST").network), str(p.link("DIST-CORESW").a_ip)))
        else:
            rows.insert(0, ("S*", "0.0.0.0/0", str(p.segment("mgmt").gateway)))
        return rows

    def neighbors(self) -> list[tuple[str, str, str]]:
        p, role = self.plan, self.dev.role
        if role == "edge":
            return [("2.2.2.2", str(p.link("EDGE-DIST").b_ip), "FULL")]
        if role == "dist":
            return [("1.1.1.1", str(p.link("EDGE-DIST").a_ip), "FULL"),
                    ("3.3.3.3", str(p.link("DIST-CORESW").b_ip), "FULL")]
        if role == "core":
            return [("2.2.2.2", str(p.link("DIST-CORESW").a_ip), "FULL")]
        return []

    def known_ips(self) -> set[str]:
        ips = set()
        for s in self.plan.segments:
            ips.add(str(s.gateway))
        for l in self.plan.links:
            ips.update({str(l.a_ip), str(l.b_ip)})
        for d in self.topo.devices:
            if d.mgmt_ip:
                ips.add(d.mgmt_ip)
        ips.update({"1.1.1.1", "8.8.8.8"})
        return ips

    # ------------------------------------------------------------------ #
    # Intérprete de comandos
    # ------------------------------------------------------------------ #
    def prompt(self) -> str:
        h, cfg = self.state.hostname, self.state.in_config
        return {"Cisco": f"{h}(config)#" if cfg else f"{h}#",
                "Huawei": f"[{h}]" if cfg else f"<{h}>",
                "Fortinet": f"{h} #", "MikroTik": f"[netadmin@{h}] >"}[self.vendor]

    def run(self, command: str) -> CommandResult:
        cmd = validate_command(command)
        t0 = time.monotonic()
        c = cmd.lower().strip()
        if re.search(r"\bping\b", c):
            out = self._ping(cmd)
        elif re.search(r"ospf|\bpeer\b|neighbor", c):
            out = self._show_ospf()
        elif re.search(r"\bint(erfaces?)?\b|ip\s+address|system\s+interface", c) and "config" not in c:
            out = self._show_interfaces()
        elif "vlan" in c:
            out = self._show_vlans()
        elif re.search(r"route|routing", c):
            out = self._show_routes()
        elif re.search(r"run|current-config|export|^show$|full-configuration", c):
            out = self._running_config()
        elif re.search(r"version|system\s+status|resource", c):
            out = self._version()
        elif c in ("?", "help", "ayuda"):
            out = self._help()
        else:
            out = f"% Comando no soportado por el simulador: '{cmd}'. Escriba 'help'."
        return CommandResult(cmd, out, elapsed_ms=int((time.monotonic() - t0) * 1000) + 12)

    def _running_config(self) -> str:
        if self.state.config_lines:                       # lo que realmente se le aplicó
            return redact_secrets("\n".join(self.state.config_lines))
        if self.state.applied >= set(ALL_CATEGORIES):     # equipo ya configurado con el diseño
            return redact_secrets(self.config_text)
        return self._factory_config()

    def _factory_config(self) -> str:
        h = self.state.hostname
        return {"Cisco": f"!\nhostname {h}\n!\ninterface GigabitEthernet0/0/0\n no ip address\n shutdown\n!\nend",
                "Huawei": f"#\nsysname {h}\n#\ninterface GigabitEthernet0/0/0\n shutdown\n#\nreturn",
                "Fortinet": f'config system global\n    set hostname "{h}"\nend',
                "MikroTik": f"/system identity set name={h}"}[self.vendor]

    def _help(self) -> str:
        return ("Comandos simulados (equivalentes por fabricante):\n"
                "  interfaces · vlan · rutas · ospf · running-config · version · ping <ip>\n"
                "  Cisco:    show ip interface brief | show vlan brief | show ip route | show ip ospf neighbor\n"
                "  Huawei:   display ip interface brief | display vlan | display ip routing-table\n"
                "  Fortinet: get system interface | get router info routing-table all | execute ping <ip>\n"
                "  MikroTik: /ip address print | /ip route print | /routing ospf neighbor print | /export")

    def _show_interfaces(self) -> str:
        rows = self.interfaces()
        up = self.has("ip") or self.has("ports")
        if not self.has("ip"):
            rows = [(n, "unassigned", 0, d) for n, _, _, d in rows]
        if self.vendor == "MikroTik" and not self.has("ip"):
            return "Flags: D - DYNAMIC\nColumns: ADDRESS, NETWORK, INTERFACE\n # (sin direcciones IP configuradas)"
        if self.vendor == "MikroTik":
            lines = ["Flags: D - DYNAMIC", "Columns: ADDRESS, NETWORK, INTERFACE",
                     " #  ADDRESS              NETWORK          INTERFACE"]
            for i, (n, ip, pl, _) in enumerate(rows):
                net = ipaddress.ip_interface(f"{ip}/{pl}").network.network_address
                lines.append(f" {i:<2} {ip + '/' + str(pl):<20} {str(net):<16} {n}")
            return "\n".join(lines)
        if self.vendor == "Fortinet":
            return "\n".join(f"== [ {n} ]\nname: {n}   mode: static   ip: "
                             + (f"{ip} {ipaddress.ip_network(f'0.0.0.0/{pl}').netmask}" if pl else "0.0.0.0 0.0.0.0")
                             + f"   status: {'up' if up else 'down'}   alias: {d}" for n, ip, pl, d in rows)
        head = ("Interface                      IP-Address      OK? Method Status                Protocol"
                if self.vendor == "Cisco" else
                "Interface                         IP Address/Mask      Physical   Protocol")
        lines = [head]
        for n, ip, pl, _ in rows:
            if self.vendor == "Cisco":
                st = "up                    up" if up else "administratively down down"
                lines.append(f"{n:<30} {ip:<15} {'YES manual' if pl else 'YES unset '} {st}")
            else:
                addr = f"{ip}/{pl}" if pl else "unassigned"
                st = "up         up" if up else "*down      down"
                lines.append(f"{n:<33} {addr:<20} {st}")
        return "\n".join(lines)

    def _show_vlans(self) -> str:
        if self.dev.role not in ("core", "access", "server"):
            return "% Este equipo es de capa 3 sin base de datos de VLAN."
        if not self.has("vlans"):
            return ("VLAN Name                             Status    Ports\n"
                    "---- -------------------------------- --------- ------------------\n"
                    "1    default                          active    (todas)")
        segs = [s for s in self.plan.segments if s.role != "dmz"]
        if self.dev.role in ("access", "server"):
            from generators.common import Ctx
            allowed = set(Ctx(None, self.plan, self.topo).trunk_vlans_for(self.dev))  # type: ignore[arg-type]
            segs = [s for s in segs if s.vlan in allowed]
        lines = ["VLAN Name                             Status    Red",
                 "---- -------------------------------- --------- ------------------"]
        for s in segs:
            lines.append(f"{s.vlan:<4} {s.tag:<32} active    {s.network}")
        lines.append("999  BLACKHOLE                        act/lshut —")
        return "\n".join(lines)

    def _show_routes(self) -> str:
        if not self.has("ip"):
            return "% La tabla de enrutamiento está vacía (no hay interfaces con IP)."
        if self.vendor == "MikroTik":
            lines = ["Flags: D - DYNAMIC; A - ACTIVE; c - CONNECT, s - STATIC, o - OSPF",
                     "    DST-ADDRESS        GATEWAY"]
            code = {"C": "DAc", "S*": "As", "O": "DAo", "O*E2": "DAo"}
            for c, dst, gw in self._visible_routes():
                lines.append(f"{code.get(c, 'A'):<4}{dst:<19} {gw}")
            return "\n".join(lines)
        lines = ["Codes: C - connected, S - static, O - OSPF, * - candidate default", ""]
        for c, dst, gw in self._visible_routes():
            via = gw if gw.startswith("directa") else f"via {gw}"
            lines.append(f"{c:<5} {dst:<20} {via}")
        return "\n".join(lines)

    def _visible_routes(self):
        rows = self.routes()
        if not self.has("routing"):
            rows = [r for r in rows if r[0] == "C" or (r[0] == "S*" and self.dev.role in ("access", "server"))]
        return rows

    def _show_ospf(self) -> str:
        if not self.has("routing"):
            return "% OSPF no está configurado en este equipo."
        nb = self.neighbors()
        if not nb:
            return "% OSPF no está habilitado en este equipo (capa 2)."
        lines = ["Neighbor ID     Pri   State           Address"]
        for rid, ip, st in nb:
            lines.append(f"{rid:<15} 0     {st}/  -        {ip}")
        return "\n".join(lines)

    def _version(self) -> str:
        from generators import ENGINES
        plat = ENGINES[self.vendor].PLATFORMS.get(self.dev.role, "")
        return (f"{self.vendor} {plat} — SIMULADO por RED-LION-INTERCONNECTION\n"
                f"Hostname: {self.state.hostname}\nGestión: {self.dev.mgmt_ip or 'N/A'}\n"
                f"Uptime: 0 weeks, 0 days (laboratorio)")

    def _ping(self, cmd: str) -> str:
        m = re.search(r"(\d{1,3}(?:\.\d{1,3}){3})", cmd)
        if not m:
            return "% Indique una dirección IPv4 destino."
        target = m.group(1)
        try:
            ipaddress.IPv4Address(target)
        except ValueError:
            return f"% Dirección inválida: {target}"
        ok = self.has("ip") and target in self.known_ips()
        if self.vendor == "Cisco":
            bang = "!!!!!" if ok else "....."
            rate = "100 percent (5/5), round-trip min/avg/max = 1/1/2 ms" if ok else "0 percent (0/5)"
            return f"Type escape sequence to abort.\nSending 5, 100-byte ICMP Echos to {target}:\n{bang}\nSuccess rate is {rate}"
        if ok:
            return "\n".join(f"Reply from {target}: bytes=56 seq={i} ttl=254 time=1 ms" for i in range(1, 6)) + \
                   "\n5 packet(s) transmitted, 5 received, 0.00% packet loss"
        return f"Request time out x5\n5 packet(s) transmitted, 0 received, 100.00% packet loss ({target})"
