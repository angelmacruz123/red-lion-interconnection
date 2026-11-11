"""
generators/huawei.py — Huawei VRP (V200R0xx / V300)
Plataformas de referencia: AR6120 (routers), S5735-L48T4X-A / S6730 (núcleo L3),
S5735-L48P4S (acceso PoE). Sintaxis compatible con eNSP para AR y S57xx.
"""

from __future__ import annotations

from core.topology import Device

from .common import BLACKHOLE_VLAN, LOCAL_AS, PROVIDER_AS, Ctx, port_plan

VENDOR = "Huawei"


def _vlan_list(vlans: list[int]) -> str:
    """Formato VRP: '20 30 40 101 to 115'."""
    vlans = sorted(set(vlans))
    out, i = [], 0
    while i < len(vlans):
        j = i
        while j + 1 < len(vlans) and vlans[j + 1] == vlans[j] + 1:
            j += 1
        out.append(f"{vlans[i]} to {vlans[j]}" if j - i >= 2 else " ".join(map(str, vlans[i:j + 1])))
        i = j + 1
    return " ".join(out)


def _hardening(ctx: Ctx, hostname: str) -> list[str]:
    mgmt = ctx.plan.segment("mgmt")
    return [
        "system-view",
        f"sysname {hostname}",
        "info-center enable",
        "header login information \"ACCESO RESTRINGIDO - Solo personal autorizado. Actividad monitoreada.\"",
        "#",
        f"acl number 2999",
        f" description ACL-MGMT",
        f" rule 5 permit source {mgmt.network.network_address} {mgmt.wildcard}",
        " rule 100 deny",
        "#",
        "aaa",
        " local-user netadmin password irreversible-cipher <<ADMIN_SECRET>>",
        " local-user netadmin privilege level 15",
        " local-user netadmin service-type ssh",
        " local-user netadmin password-force-change disable",
        "#",
        "stelnet server enable",
        "undo telnet server enable",
        "ssh server cipher aes256_ctr aes128_ctr",
        "ssh user netadmin authentication-type password",
        "ssh user netadmin service-type stelnet",
        "#",
        "user-interface vty 0 4",
        " acl 2999 inbound",
        " authentication-mode aaa",
        " protocol inbound ssh",
        " idle-timeout 10 0",
        "#",
        f"ntp-service unicast-server {ctx.extras.ntp_server}",
        "snmp-agent sys-info version v3",
        "snmp-agent group v3 NETOPS privacy",
        "snmp-agent usm-user v3 netops group NETOPS",
        "snmp-agent usm-user v3 netops authentication-mode sha cipher <<SNMPV3_AUTH>>",
        "snmp-agent usm-user v3 netops privacy-mode aes128 cipher <<SNMPV3_PRIV>>",
        "#",
        "ipv6",
        "#",
    ]


def _ospf(ctx: Ctx, dev_id: str, nets: list[tuple[str, str]], extra: list[str] = ()) -> list[str]:
    out = [f"ospf 1 router-id {ctx.router_id(dev_id)}", " bandwidth-reference 10000"]
    out += list(extra)
    out += [" area 0.0.0.0"] + [f"  network {n} {w}" for n, w in nets]
    out += ["#", f"ospfv3 1", f" router-id {ctx.router_id(dev_id)}", "#"]
    return out


def edge(ctx: Ctx, dev: Device) -> str:
    p, cfg = ctx.plan, ctx.cfg
    isp, down, dmz = p.link("ISP-EDGE"), p.link("EDGE-DIST"), p.segment("dmz")
    summ = p.summary_route
    L = _hardening(ctx, dev.hostname)

    L += ["acl number 2000", " description ACL-NAT",
          f" rule 5 permit source {summ.network_address} {summ.hostmask}"]
    if dmz:
        L.append(f" rule 10 permit source {dmz.network.network_address} {dmz.wildcard}")
    L += ["#", "acl number 3000", " description ACL-WAN-IN",
          " rule 5 deny ip source 10.0.0.0 0.255.255.255",
          " rule 10 deny ip source 172.16.0.0 0.15.255.255",
          " rule 15 deny ip source 192.168.0.0 0.0.255.255",
          " rule 20 deny ip source 127.0.0.0 0.255.255.255", "#"]

    if cfg.has("VoIP"):
        L += ["traffic classifier TC-VOZ operator or", " if-match dscp ef",
              "traffic behavior TB-VOZ", " queue ef bandwidth pct 30",
              "traffic policy TP-QOS-WAN", " classifier TC-VOZ behavior TB-VOZ", "#"]

    L += ["interface GigabitEthernet0/0/0", " description WAN-ISP",
          f" ip address {isp.b_ip} {isp.mask}", " ipv6 enable",
          f" ipv6 address {isp.b_ip6} 127", " nat outbound 2000",
          " traffic-filter inbound acl 3000",
          f" qos lr cir {cfg.isp_bandwidth_mbps * 1000}"]
    if cfg.has("VoIP"):
        L.append(" traffic-policy TP-QOS-WAN outbound")
    L += ["#", "interface GigabitEthernet0/0/1", f" description P2P-{down.b_device}",
          f" ip address {down.a_ip} {down.mask}", " ipv6 enable",
          f" ipv6 address {down.a_ip6} 127", " ospf network-type p2p",
          " ospfv3 1 area 0.0.0.0", "#"]
    if dmz:
        L += ["interface GigabitEthernet0/0/2", " description DMZ",
              f" ip address {dmz.gateway} {dmz.mask}", " ipv6 enable",
              f" ipv6 address {dmz.ipv6_gateway} 64", " ospfv3 1 area 0.0.0.0", "#"]

    rnet, rmask, _ = ctx.extras.remote_lan_parts()
    peer = ctx.extras.peer_public_ip
    if cfg.vpn_type == "IPsec" and p.tunnel:
        t = p.tunnel
        L += ["ipsec proposal PROP-AES256", " esp authentication-algorithm sha2-256",
              " esp encryption-algorithm aes-256", "#",
              "ike proposal 10", " encryption-algorithm aes-256", " dh group19",
              " authentication-algorithm sha2-256", " integrity-algorithm hmac-sha2-256", "#",
              "ike peer SEDE-REMOTA", " undo version 1", " pre-shared-key cipher <<VPN_PSK>>",
              " ike-proposal 10", f" remote-address {peer}", "#",
              "ipsec profile IPSEC-REMOTO", " ike-peer SEDE-REMOTA", " proposal PROP-AES256", "#",
              "interface Tunnel0/0/0", " description VTI-IPSEC-SEDE-REMOTA",
              f" ip address {t.a_ip} {t.mask}", " tunnel-protocol ipsec",
              " source GigabitEthernet0/0/0", f" destination {peer}",
              " ipsec profile IPSEC-REMOTO", " tcp adjust-mss 1360", "#",
              f"ip route-static {rnet} {rmask} Tunnel0/0/0 description LAN-REMOTA"]
    elif cfg.vpn_type == "MPLS" and p.tunnel:
        t = p.tunnel
        L += ["interface GigabitEthernet0/0/3", " description CE-PE-MPLS",
              f" ip address {t.a_ip} {t.mask}", "#",
              f"bgp {LOCAL_AS}", f" peer {t.b_ip} as-number {PROVIDER_AS}",
              f" peer {t.b_ip} description PE-MPLS", " ipv4-family unicast",
              f"  network {summ.network_address} {summ.prefixlen}",
              f"  peer {t.b_ip} enable", "#",
              f"ip route-static {summ.network_address} {summ.netmask} NULL0 preference 254"]
    elif cfg.vpn_type == "SSL":
        L += ["# SSL VPN: los AR6000 la ofrecen solo con licencia específica;",
              "# se recomienda terminarla en un firewall USG/FortiGate."]
    L += ["#", f"ip route-static 0.0.0.0 0.0.0.0 {isp.a_ip} description DEFAULT-ISP",
          f"ipv6 route-static :: 0 {isp.a_ip6}", "#"]
    nets = [(str(down.network.network_address), down.wildcard)]
    if dmz:
        nets.append((str(dmz.network.network_address), dmz.wildcard))
    extra = [" default-route-advertise always"] + ([" silent-interface GigabitEthernet0/0/2"] if dmz else [])
    L += _ospf(ctx, dev.id, nets, extra)
    L += ["ospfv3 1", " default-route-advertise always", "#", "return", "save"]
    return "\n".join(L)


def dist(ctx: Ctx, dev: Device) -> str:
    p = ctx.plan
    up, down = p.link("EDGE-DIST"), p.link("DIST-CORESW")
    L = _hardening(ctx, dev.hostname)
    for ifn, link, ip, ip6, peer in (("GigabitEthernet0/0/0", up, up.b_ip, up.b_ip6, up.a_device),
                                     ("GigabitEthernet0/0/1", down, down.a_ip, down.a_ip6, down.b_device)):
        L += [f"interface {ifn}", f" description P2P-{peer}",
              f" ip address {ip} {link.mask}", " ipv6 enable", f" ipv6 address {ip6} 127",
              " ospf network-type p2p", " ospfv3 1 area 0.0.0.0", "#"]
    L += _ospf(ctx, dev.id, [(str(up.network.network_address), up.wildcard),
                             (str(down.network.network_address), down.wildcard)])
    L += ["return", "save"]
    return "\n".join(L)


def core(ctx: Ctx, dev: Device) -> str:
    p = ctx.plan
    up = p.link("DIST-CORESW")
    L = _hardening(ctx, dev.hostname)
    L += [f"vlan batch {_vlan_list([s.vlan for s in ctx.core_segments] + [BLACKHOLE_VLAN])}", "#",
          "stp mode rstp", "stp root primary", "stp bpdu-protection", "#",
          "dhcp enable", "dhcp snooping enable", "#"]
    for seg in ctx.core_segments:
        L += [f"vlan {seg.vlan}", f" name {seg.tag}", "#"]

    L += ["interface XGigabitEthernet0/0/1", " description P2P-R-DIST", " undo portswitch",
          f" ip address {up.b_ip} {up.mask}", " ipv6 enable", f" ipv6 address {up.b_ip6} 127",
          " ospf network-type p2p", " ospfv3 1 area 0.0.0.0", "#"]

    dhcp_vlans = {s.vlan for s in ctx.dhcp_segments}
    for seg in ctx.core_segments:
        L += [f"interface Vlanif{seg.vlan}", f" description GW-{seg.tag}",
              f" ip address {seg.gateway} {seg.mask}", " ipv6 enable",
              f" ipv6 address {seg.ipv6_gateway} 64", " ospfv3 1 area 0.0.0.0"]
        if seg.vlan in dhcp_vlans:
            L.append(" dhcp select global")
        L.append("#")

    for seg in ctx.dhcp_segments:
        L += [f"ip pool POOL-{seg.tag}", f" gateway-list {seg.gateway}",
              f" network {seg.network.network_address} mask {seg.mask}",
              f" excluded-ip-address {seg.first_host} {seg.network.network_address + seg.reserved_static}",
              f" dns-list {' '.join(ctx.extras.dns_servers)}",
              f" domain-name {ctx.extras.domain}", " lease day 0 hour 8", "#"]

    for d in [x for x in ctx.topo.devices if x.role in ("access", "server")]:
        L += [f"interface GigabitEthernet0/0/{ctx.access_index(d)}",
              f" description TRUNK-{d.hostname}", " port link-type trunk",
              f" port trunk pvid vlan {BLACKHOLE_VLAN}",
              f" undo port trunk allow-pass vlan 1",
              f" port trunk allow-pass vlan {_vlan_list(ctx.trunk_vlans_for(d))}",
              " dhcp snooping trusted", "#"]

    nets = [(str(up.network.network_address), up.wildcard)]
    nets += [(str(s.network.network_address), s.wildcard) for s in ctx.core_segments]
    extra = [" silent-interface all", " undo silent-interface XGigabitEthernet0/0/1"]
    L += _ospf(ctx, dev.id, nets, extra)
    L += ["return", "save"]
    return "\n".join(L)


def access(ctx: Ctx, dev: Device) -> str:
    p = ctx.plan
    mgmt, voice = p.segment("mgmt"), p.segment("voice")
    vlans = ctx.trunk_vlans_for(dev)
    L = _hardening(ctx, dev.hostname)
    L += [f"vlan batch {_vlan_list(vlans + [BLACKHOLE_VLAN])}", "#",
          "stp mode rstp", "stp bpdu-protection", "dhcp enable", "dhcp snooping enable",
          f"dhcp snooping enable vlan {_vlan_list(vlans)}", "#"]
    if voice:
        L += [f"voice-vlan mac-address 0001-e300-0000 mask ffff-ff00-0000 description PHONES", "#"]
    L += [f"interface Vlanif{mgmt.vlan}", " description GESTION",
          f" ip address {dev.mgmt_ip} {mgmt.mask}", "#",
          f"ip route-static 0.0.0.0 0.0.0.0 {mgmt.gateway}", "#"]

    for g in port_plan(ctx, dev):
        if g.start == g.end:
            L.append(f"interface GigabitEthernet0/0/{g.start}")
        else:
            L.append(f"port-group group-member GigabitEthernet0/0/{g.start} to GigabitEthernet0/0/{g.end}")
        if g.kind in ("user", "server"):
            L += [" port link-type hybrid", f" port hybrid pvid vlan {g.vlan}",
                  f" port hybrid untagged vlan {g.vlan}"]
            if g.kind == "user" and voice:
                L += [f" port hybrid tagged vlan {voice.vlan}", f" voice-vlan {voice.vlan} enable"]
            L += [" stp edged-port enable", " port-security enable",
                  f" port-security max-mac-num {3 if g.kind == 'user' else 2}",
                  " port-security protect-action restrict", " undo shutdown"]
        elif g.kind == "camera":
            L += [" port link-type access", f" port default vlan {g.vlan}",
                  " poe enable", " stp edged-port enable", " undo shutdown"]
        elif g.kind == "ap":
            wifi = p.segment("wifi")
            L += [" port link-type trunk", f" port trunk pvid vlan {mgmt.vlan}",
                  f" port trunk allow-pass vlan {mgmt.vlan} {wifi.vlan}", " poe enable",
                  " stp edged-port enable", " undo shutdown"]
        else:
            L += [" port link-type access", f" port default vlan {BLACKHOLE_VLAN}", " shutdown"]
        L.append("#")

    L += ["interface XGigabitEthernet0/0/1", " description UPLINK-SW-CORE",
          " port link-type trunk", f" port trunk pvid vlan {BLACKHOLE_VLAN}",
          " undo port trunk allow-pass vlan 1",
          f" port trunk allow-pass vlan {_vlan_list(vlans)}", " dhcp snooping trusted",
          "#", "return", "save"]
    return "\n".join(L)


PLATFORMS = {"edge": "AR6120", "dist": "AR6120", "core": "S6730-H48X6C",
             "access": "S5735-L48P4X", "server": "S5735-L48T4X"}
RENDER = {"edge": edge, "dist": dist, "core": core, "access": access, "server": access}
COMMENT = "#"
