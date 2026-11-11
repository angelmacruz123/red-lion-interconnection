"""
generators/cisco.py — Cisco IOS / IOS-XE
Plataformas de referencia: ISR 4331 (routers), Catalyst 9300 (núcleo L3),
Catalyst 9200-48P (acceso). La mayoría de comandos también funcionan en
Packet Tracer (ISR4331 / 3650-24PS); IKEv2, scrypt y QoS dependen de la versión.
"""

from __future__ import annotations

from core.ipam import Segment
from core.topology import Device

from .common import (BLACKHOLE_VLAN, LOCAL_AS, PROVIDER_AS, Ctx, port_plan, prefix_str,
                     ranges)

VENDOR = "Cisco"


def _hardening(ctx: Ctx, hostname: str) -> list[str]:
    mgmt = ctx.plan.segment("mgmt")
    return [
        f"hostname {hostname}",
        "no ip domain-lookup",
        f"ip domain-name {ctx.extras.domain}",
        "service password-encryption",
        "service timestamps log datetime msec",
        "security passwords min-length 12",
        "login block-for 120 attempts 3 within 60",
        "enable algorithm-type scrypt secret <<ENABLE_SECRET>>",
        "username netadmin privilege 15 algorithm-type scrypt secret <<ADMIN_SECRET>>",
        "crypto key generate rsa general-keys modulus 2048",
        "ip ssh version 2",
        "ip ssh time-out 60",
        "ip ssh authentication-retries 3",
        "banner motd ^C",
        "  ACCESO RESTRINGIDO - Solo personal autorizado. Actividad monitoreada.",
        "^C",
        "!",
        "ip access-list standard ACL-MGMT",
        f" permit {mgmt.network.network_address} {mgmt.wildcard}",
        " deny any log",
        "!",
        "line con 0",
        " logging synchronous",
        " exec-timeout 10 0",
        " login local",
        "line vty 0 15",
        " access-class ACL-MGMT in",
        " transport input ssh",
        " exec-timeout 10 0",
        " login local",
        "!",
        f"ntp server {ctx.extras.ntp_server}",
        "snmp-server group NETOPS v3 priv",
        "snmp-server user netops NETOPS v3 auth sha <<SNMPV3_AUTH>> priv aes 128 <<SNMPV3_PRIV>>",
        "!",
    ]


def _ospf(ctx: Ctx, device_id: str, networks: list[tuple[str, str]], extra: list[str] = (),
          extra6: list[str] = ()) -> list[str]:
    out = ["router ospf 1", f" router-id {ctx.router_id(device_id)}", " auto-cost reference-bandwidth 10000"]
    out += [f" network {n} {w} area 0" for n, w in networks]
    out += list(extra)
    out += ["!", "ipv6 router ospf 1", f" router-id {ctx.router_id(device_id)}"] + list(extra6) + ["!"]
    return out


def edge(ctx: Ctx, dev: Device) -> str:
    p, cfg = ctx.plan, ctx.cfg
    isp, down = p.link("ISP-EDGE"), p.link("EDGE-DIST")
    dmz = p.segment("dmz")
    summ = p.summary_route
    L = _hardening(ctx, dev.hostname) + ["ipv6 unicast-routing", "!"]

    # QoS VoIP (LLQ) ------------------------------------------------------
    if cfg.has("VoIP"):
        L += [
            "class-map match-any CM-VOZ",
            " match dscp ef",
            "class-map match-any CM-SENAL",
            " match dscp cs3 af31",
            "policy-map PM-QOS-WAN",
            " class CM-VOZ",
            "  priority percent 30",
            " class CM-SENAL",
            "  bandwidth percent 5",
            " class class-default",
            "  fair-queue",
            f"policy-map PM-SHAPE-ISP",
            " class class-default",
            f"  shape average {cfg.isp_bandwidth_mbps * 1_000_000}",
            "  service-policy PM-QOS-WAN",
            "!",
        ]

    # ACL de entrada WAN (anti-spoofing + retorno de sesiones)
    L += [
        "ip access-list extended ACL-WAN-IN",
        " remark --- Anti-spoofing RFC 1918 / bogons ---",
        " deny ip 10.0.0.0 0.255.255.255 any",
        " deny ip 172.16.0.0 0.15.255.255 any",
        " deny ip 192.168.0.0 0.0.255.255 any",
        " deny ip 127.0.0.0 0.255.255.255 any",
        " remark --- Retorno de tráfico legítimo ---",
        " permit tcp any any established",
        " permit udp any eq domain any",
        " permit udp any eq ntp any",
        " permit icmp any any echo-reply",
        " permit icmp any any unreachable",
        " permit icmp any any time-exceeded",
    ]
    if cfg.vpn_type == "IPsec":
        L += [f" permit udp host {ctx.extras.peer_public_ip} any eq isakmp",
              f" permit udp host {ctx.extras.peer_public_ip} any eq non500-isakmp",
              f" permit esp host {ctx.extras.peer_public_ip} any"]
    L += [" deny ip any any log", "!"]

    # Interfaces -----------------------------------------------------------
    L += [
        "interface GigabitEthernet0/0/0",
        " description WAN-ISP",
        f" ip address {isp.b_ip} {isp.mask}",
        f" ipv6 address {isp.b_ip6}/127",
        " ip nat outside",
        " ip access-group ACL-WAN-IN in",
        " no ip redirects",
        " no ip unreachables",
        " no ip proxy-arp",
    ]
    if cfg.has("VoIP"):
        L.append(" service-policy output PM-SHAPE-ISP")
    L += [" no shutdown", "!",
          "interface GigabitEthernet0/0/1",
          f" description P2P-{down.b_device}",
          f" ip address {down.a_ip} {down.mask}",
          f" ipv6 address {down.a_ip6}/127",
          " ip nat inside",
          " ip ospf network point-to-point",
          " ipv6 ospf 1 area 0",
          " no shutdown", "!"]
    if dmz:
        L += ["interface GigabitEthernet0/0/2",
              " description DMZ",
              f" ip address {dmz.gateway} {dmz.mask}",
              f" ipv6 address {dmz.ipv6_gateway}/64",
              " ip nat inside",
              " ipv6 ospf 1 area 0",
              " no shutdown", "!"]

    # VPN ------------------------------------------------------------------
    rnet, rmask, _ = ctx.extras.remote_lan_parts()
    if cfg.vpn_type == "IPsec" and p.tunnel:
        t = p.tunnel
        peer = ctx.extras.peer_public_ip
        L += [
            "crypto ikev2 proposal PROP-AES256",
            " encryption aes-cbc-256",
            " integrity sha256",
            " group 19",
            "crypto ikev2 policy POL-IKEV2",
            " proposal PROP-AES256",
            "crypto ikev2 keyring KR-REMOTO",
            " peer SEDE-REMOTA",
            f"  address {peer}",
            "  pre-shared-key <<VPN_PSK>>",
            "crypto ikev2 profile PRF-REMOTO",
            f" match identity remote address {peer} 255.255.255.255",
            " authentication remote pre-share",
            " authentication local pre-share",
            " keyring local KR-REMOTO",
            "crypto ipsec transform-set TS-GCM256 esp-gcm 256",
            " mode tunnel",
            "crypto ipsec profile IPSEC-REMOTO",
            " set transform-set TS-GCM256",
            " set ikev2-profile PRF-REMOTO",
            "!",
            "interface Tunnel0",
            " description VTI-IPSEC-SEDE-REMOTA",
            f" ip address {t.a_ip} {t.mask}",
            f" ipv6 address {t.a_ip6}/127",
            " ip mtu 1400",
            " ip tcp adjust-mss 1360",
            " tunnel source GigabitEthernet0/0/0",
            f" tunnel destination {peer}",
            " tunnel mode ipsec ipv4",
            " tunnel protection ipsec profile IPSEC-REMOTO",
            "!",
            f"ip route {rnet} {rmask} Tunnel0 {t.b_ip}",
        ]
    elif cfg.vpn_type == "MPLS" and p.tunnel:
        t = p.tunnel
        L += [
            "interface GigabitEthernet0/1/0",
            " description CE-PE-MPLS-PROVEEDOR",
            f" ip address {t.a_ip} {t.mask}",
            " no shutdown",
            "!",
            f"router bgp {LOCAL_AS}",
            " bgp log-neighbor-changes",
            f" neighbor {t.b_ip} remote-as {PROVIDER_AS}",
            f" neighbor {t.b_ip} description PE-MPLS",
            " address-family ipv4",
            f"  network {summ.network_address} mask {summ.netmask}",
            f"  neighbor {t.b_ip} activate",
            " exit-address-family",
            f"ip route {summ.network_address} {summ.netmask} Null0 254",
        ]
    elif cfg.vpn_type == "SSL":
        L += ["! SSL VPN: IOS/IOS-XE en ISR no termina AnyConnect.",
              "! Termine SSL VPN en un ASA/FTD o use el perfil Fortinet de esta herramienta."]
    L.append("!")

    # NAT y enrutamiento ---------------------------------------------------
    L += ["ip access-list standard ACL-NAT",
          f" permit {summ.network_address} {summ.hostmask}"]
    if dmz:
        L.append(f" permit {dmz.network.network_address} {dmz.wildcard}")
    L += ["ip nat inside source list ACL-NAT interface GigabitEthernet0/0/0 overload", "!",
          f"ip route 0.0.0.0 0.0.0.0 {isp.a_ip} name DEFAULT-ISP",
          f"ipv6 route ::/0 {isp.a_ip6}", "!"]
    nets = [(str(down.network.network_address), down.wildcard)]
    if dmz:
        nets.append((str(dmz.network.network_address), dmz.wildcard))
    extra = [" passive-interface GigabitEthernet0/0/2"] if dmz else []
    extra += [" default-information originate"]
    L += _ospf(ctx, dev.id, nets, extra, [" default-information originate"])
    L += ["end", "write memory"]
    return "\n".join(L)


def dist(ctx: Ctx, dev: Device) -> str:
    p = ctx.plan
    up, down = p.link("EDGE-DIST"), p.link("DIST-CORESW")
    L = _hardening(ctx, dev.hostname) + ["ipv6 unicast-routing", "!"]
    for ifname, link, ip, ip6, peer in (
        ("GigabitEthernet0/0/0", up, up.b_ip, up.b_ip6, up.a_device),
        ("GigabitEthernet0/0/1", down, down.a_ip, down.a_ip6, down.b_device),
    ):
        L += [f"interface {ifname}", f" description P2P-{peer}",
              f" ip address {ip} {link.mask}", f" ipv6 address {ip6}/127",
              " ip ospf network point-to-point", " ipv6 ospf 1 area 0",
              " no shutdown", "!"]
    L += _ospf(ctx, dev.id, [(str(up.network.network_address), up.wildcard),
                             (str(down.network.network_address), down.wildcard)])
    L += ["end", "write memory"]
    return "\n".join(L)


def _svi(seg: Segment, passive: bool = True) -> list[str]:
    return [f"interface Vlan{seg.vlan}",
            f" description GW-{seg.tag}",
            f" ip address {seg.gateway} {seg.mask}",
            f" ipv6 address {seg.ipv6_gateway}/64",
            " ipv6 nd other-config-flag",
            " ipv6 ospf 1 area 0",
            " no ip redirects",
            " no shutdown", "!"]


def core(ctx: Ctx, dev: Device) -> str:
    p = ctx.plan
    up = p.link("DIST-CORESW")
    L = _hardening(ctx, dev.hostname)
    L += ["ip routing", "ipv6 unicast-routing", "spanning-tree mode rapid-pvst",
          "spanning-tree extend system-id",
          f"spanning-tree vlan 1-4094 priority 4096",
          "vtp mode transparent", "!"]
    for seg in ctx.core_segments:
        L += [f"vlan {seg.vlan}", f" name {seg.tag}"]
    L += [f"vlan {BLACKHOLE_VLAN}", " name BLACKHOLE", "!"]

    # Uplink enrutado hacia R-DIST
    L += ["interface TenGigabitEthernet1/1/1", " description P2P-R-DIST", " no switchport",
          f" ip address {up.b_ip} {up.mask}", f" ipv6 address {up.b_ip6}/127",
          " ip ospf network point-to-point", " ipv6 ospf 1 area 0", " no shutdown", "!"]

    for seg in ctx.core_segments:
        L += _svi(seg)

    # Downlinks troncales a cada switch de acceso / servidores
    for d in [x for x in ctx.topo.devices if x.role in ("access", "server")]:
        port = ctx.access_index(d)
        L += [f"interface GigabitEthernet1/0/{port}",
              f" description TRUNK-{d.hostname}",
              " switchport mode trunk",
              f" switchport trunk native vlan {BLACKHOLE_VLAN}",
              f" switchport trunk allowed vlan {ranges(ctx.trunk_vlans_for(d))}",
              " switchport nonegotiate",
              " ip dhcp snooping trust",
              " no shutdown", "!"]

    # DHCP ----------------------------------------------------------------
    for seg in ctx.dhcp_segments:
        L.append(f"ip dhcp excluded-address {seg.first_host} "
                 f"{seg.network.network_address + seg.reserved_static}")
    for seg in ctx.dhcp_segments:
        L += [f"ip dhcp pool POOL-{seg.tag}",
              f" network {seg.network.network_address} {seg.mask}",
              f" default-router {seg.gateway}",
              f" dns-server {' '.join(ctx.extras.dns_servers)}",
              f" domain-name {ctx.extras.domain}",
              " lease 0 8"]
    L.append("!")

    nets = [(str(up.network.network_address), up.wildcard)]
    nets += [(str(s.network.network_address), s.wildcard) for s in ctx.core_segments]
    extra = [" passive-interface default", " no passive-interface TenGigabitEthernet1/1/1"]
    L += _ospf(ctx, dev.id, nets, extra, [" passive-interface default",
                                          " no passive-interface TenGigabitEthernet1/1/1"])
    L += ["end", "write memory"]
    return "\n".join(L)


def access(ctx: Ctx, dev: Device) -> str:
    p = ctx.plan
    mgmt = p.segment("mgmt")
    voice = p.segment("voice")
    vlans = ctx.trunk_vlans_for(dev)
    L = _hardening(ctx, dev.hostname)
    L += ["spanning-tree mode rapid-pvst", "spanning-tree portfast bpduguard default",
          "vtp mode transparent", "!"]
    by_vlan = {s.vlan: s for s in p.segments}
    for v in vlans:
        L += [f"vlan {v}", f" name {by_vlan[v].tag}"]
    L += [f"vlan {BLACKHOLE_VLAN}", " name BLACKHOLE", "!",
          "ip dhcp snooping", f"ip dhcp snooping vlan {ranges(vlans)}",
          "no ip dhcp snooping information option", "!"]
    L += [f"interface Vlan{mgmt.vlan}", " description GESTION",
          f" ip address {dev.mgmt_ip} {mgmt.mask}", " no shutdown", "!",
          f"ip default-gateway {mgmt.gateway}", "!"]

    for g in port_plan(ctx, dev):
        rng = f"GigabitEthernet1/0/{g.start}" + (f" - {g.end}" if g.end != g.start else "")
        L.append(f"interface range {rng}")
        if g.kind in ("user", "server"):
            L += [f" description {'USUARIOS' if g.kind == 'user' else 'SERVIDORES'}",
                  " switchport mode access", f" switchport access vlan {g.vlan}"]
            if g.kind == "user" and voice:
                L += [f" switchport voice vlan {voice.vlan}", " trust device cisco-phone"]
            L += [" switchport port-security",
                  f" switchport port-security maximum {3 if g.kind == 'user' else 2}",
                  " switchport port-security violation restrict",
                  " switchport port-security aging time 10",
                  " spanning-tree portfast", " spanning-tree bpduguard enable",
                  " ip dhcp snooping limit rate 15", " no shutdown"]
        elif g.kind == "camera":
            L += [" description CAMARAS-CCTV", " switchport mode access",
                  f" switchport access vlan {g.vlan}", " power inline auto",
                  " spanning-tree portfast", " no shutdown"]
        elif g.kind == "ap":
            wifi = p.segment("wifi")
            L += [" description ACCESS-POINTS", " switchport mode trunk",
                  f" switchport trunk native vlan {mgmt.vlan}",
                  f" switchport trunk allowed vlan {mgmt.vlan},{wifi.vlan}",
                  " power inline auto", " spanning-tree portfast trunk", " no shutdown"]
        else:
            L += [" description NO-USADO", " switchport mode access",
                  f" switchport access vlan {BLACKHOLE_VLAN}", " shutdown"]
        L.append("!")

    L += ["interface GigabitEthernet1/1/1", " description UPLINK-SW-CORE",
          " switchport mode trunk", f" switchport trunk native vlan {BLACKHOLE_VLAN}",
          f" switchport trunk allowed vlan {ranges(vlans)}", " switchport nonegotiate",
          " ip dhcp snooping trust", " no shutdown", "!", "end", "write memory"]
    return "\n".join(L)


PLATFORMS = {"edge": "ISR 4331", "dist": "ISR 4331", "core": "Catalyst 9300-48P",
             "access": "Catalyst 9200-48P", "server": "Catalyst 9200-48T"}
RENDER = {"edge": edge, "dist": dist, "core": core, "access": access, "server": access}
COMMENT = "!"
