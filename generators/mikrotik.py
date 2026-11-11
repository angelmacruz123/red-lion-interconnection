"""
generators/mikrotik.py — MikroTik RouterOS v7
Plataformas de referencia: CCR2004-16G-2S+ (borde y distribución),
CRS518-16XS-2XQ (núcleo L3 con offload L3HW), CRS354-48P-4S+2Q+ (acceso PoE).

Buena práctica aplicada: `vlan-filtering=yes` se activa AL FINAL del script
para no perder la gestión durante la aplicación.
"""

from __future__ import annotations

from core.topology import Device

from .common import BLACKHOLE_VLAN, LOCAL_AS, PROVIDER_AS, Ctx, port_plan, prefix_str

VENDOR = "MikroTik"


def _hardening(ctx: Ctx, hostname: str) -> list[str]:
    mgmt = prefix_str(ctx.plan.segment("mgmt").network)
    return [
        f"/system identity set name={hostname}",
        '/system note set note="ACCESO RESTRINGIDO - Solo personal autorizado. Actividad monitoreada." show-at-login=yes',
        f'/user add name=netadmin group=full password="<<ADMIN_SECRET>>" address={mgmt}',
        "/user set admin disabled=yes",
        "/ip service disable telnet,ftp,www,api,api-ssl",
        f"/ip service set ssh port=22 address={mgmt}",
        f"/ip service set winbox address={mgmt}",
        "/ip ssh set strong-crypto=yes",
        "/tool mac-server set allowed-interface-list=none",
        "/tool mac-server mac-winbox set allowed-interface-list=none",
        "/ip neighbor discovery-settings set discover-interface-list=none",
        f"/system ntp client set enabled=yes servers={ctx.extras.ntp_server}",
        "/snmp community set [find default=yes] disabled=yes",
        '/snmp community add name=netops security=private authentication-protocol=SHA1 '
        'authentication-password="<<SNMPV3_AUTH>>" encryption-protocol=AES '
        'encryption-password="<<SNMPV3_PRIV>>"',
    ]


def _ospf(ctx: Ctx, dev_id: str, v4_nets: list[str], interfaces6: list[str], originate: bool = False,
          passive_v4: list[str] = ()) -> list[str]:
    rid = ctx.router_id(dev_id)
    orig = " originate-default=always" if originate else ""
    L = [f"/routing ospf instance add name=ospf-v2 version=2 router-id={rid}{orig}",
         "/routing ospf area add name=backbone-v2 area-id=0.0.0.0 instance=ospf-v2",
         f"/routing ospf interface-template add area=backbone-v2 networks={','.join(v4_nets)}",
         f"/routing ospf instance add name=ospf-v3 version=3 router-id={rid}{orig}",
         "/routing ospf area add name=backbone-v3 area-id=0.0.0.0 instance=ospf-v3"]
    if passive_v4:
        L.insert(3, f"/routing ospf interface-template add area=backbone-v2 networks={','.join(passive_v4)} passive=yes")
    if interfaces6:
        L.append(f"/routing ospf interface-template add area=backbone-v3 interfaces={','.join(interfaces6)}")
    return L


def edge(ctx: Ctx, dev: Device) -> str:
    p, cfg = ctx.plan, ctx.cfg
    isp, down, dmz, summ = p.link("ISP-EDGE"), p.link("EDGE-DIST"), p.segment("dmz"), p.summary_route
    mgmt = prefix_str(p.segment("mgmt").network)
    L = _hardening(ctx, dev.hostname)
    L += ["/interface ethernet set [find default-name=ether1] comment=WAN-ISP",
          "/interface ethernet set [find default-name=ether2] comment=P2P-R-DIST",
          "/interface list add name=WAN", "/interface list add name=LAN",
          "/interface list member add list=WAN interface=ether1",
          "/interface list member add list=LAN interface=ether2",
          f"/ip address add address={isp.b_ip}/30 interface=ether1 comment=WAN-ISP",
          f"/ip address add address={down.a_ip}/30 interface=ether2 comment=P2P-R-DIST",
          f"/ipv6 address add address={isp.b_ip6}/127 interface=ether1 advertise=no",
          f"/ipv6 address add address={down.a_ip6}/127 interface=ether2 advertise=no"]
    if dmz:
        L += ["/interface ethernet set [find default-name=ether3] comment=DMZ",
              "/interface list member add list=LAN interface=ether3",
              f"/ip address add address={dmz.gateway}/{dmz.prefix} interface=ether3 comment=DMZ",
              f"/ipv6 address add address={dmz.ipv6_gateway}/64 interface=ether3"]
    L += [f"/ip route add dst-address=0.0.0.0/0 gateway={isp.a_ip} comment=DEFAULT-ISP",
          f"/ipv6 route add dst-address=::/0 gateway={isp.a_ip6}",
          f"/ip firewall address-list add list=LAN-CORP address={prefix_str(summ)}"]
    if dmz:
        L.append(f"/ip firewall address-list add list=LAN-CORP address={prefix_str(dmz.network)}")

    # Firewall stateful -----------------------------------------------------
    L += ["/ip firewall filter",
          "add chain=input action=accept connection-state=established,related,untracked comment=\"Retorno\"",
          "add chain=input action=drop connection-state=invalid",
          "add chain=input action=accept protocol=icmp",
          f"add chain=input action=accept protocol=tcp dst-port=22,8291 src-address={mgmt} comment=\"Gestion\"",
          "add chain=input action=accept protocol=ospf in-interface=ether2"]
    if cfg.vpn_type == "IPsec":
        L += ["add chain=input action=accept protocol=udp dst-port=500,4500 in-interface-list=WAN",
              "add chain=input action=accept protocol=ipsec-esp in-interface-list=WAN"]
    if cfg.vpn_type == "SSL":
        L += ["add chain=input action=accept protocol=tcp dst-port=443 in-interface-list=WAN comment=\"SSTP\""]
    L += ["add chain=input action=drop comment=\"Denegar resto\"",
          "add chain=forward action=fasttrack-connection connection-state=established,related hw-offload=yes",
          "add chain=forward action=accept connection-state=established,related,untracked",
          "add chain=forward action=drop connection-state=invalid",
          "add chain=forward action=accept ipsec-policy=in,ipsec",
          "add chain=forward action=accept ipsec-policy=out,ipsec",
          "add chain=forward action=accept src-address-list=LAN-CORP out-interface-list=WAN",
          "add chain=forward action=accept in-interface=ether2 out-interface=ether3" if dmz else "",
          "add chain=forward action=drop in-interface-list=WAN connection-nat-state=!dstnat comment=\"Bloquear WAN\""]
    L = [x for x in L if x]
    L += ["/ip firewall nat",
          "add chain=srcnat action=accept ipsec-policy=out,ipsec comment=\"No NAT hacia VPN\"",
          "add chain=srcnat action=masquerade out-interface-list=WAN src-address-list=LAN-CORP"]

    if cfg.has("VoIP"):
        bw = cfg.isp_bandwidth_mbps
        L += ["/ip firewall mangle add chain=forward dscp=46 action=mark-packet new-packet-mark=voz passthrough=no",
              f"/queue tree add name=WAN-OUT parent=ether1 max-limit={bw}M",
              f"/queue tree add name=VOZ parent=WAN-OUT packet-mark=voz priority=1 limit-at={int(bw * 0.3)}M max-limit={bw}M",
              f"/queue tree add name=RESTO parent=WAN-OUT packet-mark=no-mark priority=8 max-limit={bw}M"]

    peer = ctx.extras.peer_public_ip
    rnet = ctx.extras.remote_lan if ctx.extras.remote_lan_net else "<<REMOTE_LAN_CIDR>>"
    if cfg.vpn_type == "IPsec" and p.tunnel:
        L += ["/ip ipsec profile add name=IKE2-AES256 hash-algorithm=sha256 enc-algorithm=aes-256 dh-group=ecp256",
              f"/ip ipsec peer add name=SEDE-REMOTA address={peer}/32 exchange-mode=ike2 profile=IKE2-AES256",
              "/ip ipsec proposal add name=P2-GCM256 auth-algorithms=\"\" enc-algorithms=aes-256-gcm pfs-group=ecp256",
              '/ip ipsec identity add peer=SEDE-REMOTA auth-method=pre-shared-key secret="<<VPN_PSK>>"',
              f"/ip ipsec policy add peer=SEDE-REMOTA tunnel=yes src-address={prefix_str(summ)} "
              f"dst-address={rnet} proposal=P2-GCM256"]
    elif cfg.vpn_type == "SSL":
        L += ["# SSL VPN en RouterOS = SSTP (TLS/443). Requiere certificado válido importado.",
              "/ip pool add name=POOL-SSTP ranges=10.212.134.200-10.212.134.210",
              f"/ppp profile add name=SSTP-PROFILE local-address={down.a_ip} remote-address=POOL-SSTP use-encryption=required",
              "/interface sstp-server server set enabled=yes default-profile=SSTP-PROFILE "
              "authentication=mschap2 certificate=<<CERT_NAME>> tls-version=only-1.2"]
    elif cfg.vpn_type == "MPLS" and p.tunnel:
        t = p.tunnel
        L += ["/interface ethernet set [find default-name=ether4] comment=CE-PE-MPLS",
              f"/ip address add address={t.a_ip}/30 interface=ether4",
              f"/ip firewall address-list add list=BGP-OUT address={prefix_str(summ)}",
              f"/routing bgp connection add name=PE-MPLS as={LOCAL_AS} local.role=ebgp "
              f"remote.address={t.b_ip} remote.as={PROVIDER_AS} output.network=BGP-OUT",
              f"/ip route add dst-address={prefix_str(summ)} blackhole distance=254"]

    v4 = [prefix_str(down.network)] + ([prefix_str(dmz.network)] if dmz else [])
    L += _ospf(ctx, dev.id, v4, ["ether2"] + (["ether3"] if dmz else []), originate=True)
    return "\n".join(L)


def dist(ctx: Ctx, dev: Device) -> str:
    p = ctx.plan
    up, down = p.link("EDGE-DIST"), p.link("DIST-CORESW")
    L = _hardening(ctx, dev.hostname)
    L += ["/interface ethernet set [find default-name=ether1] comment=P2P-R-CORE",
          "/interface ethernet set [find default-name=ether2] comment=P2P-SW-CORE",
          f"/ip address add address={up.b_ip}/30 interface=ether1",
          f"/ip address add address={down.a_ip}/30 interface=ether2",
          f"/ipv6 address add address={up.b_ip6}/127 interface=ether1 advertise=no",
          f"/ipv6 address add address={down.a_ip6}/127 interface=ether2 advertise=no"]
    L += _ospf(ctx, dev.id, [prefix_str(up.network), prefix_str(down.network)], ["ether1", "ether2"])
    return "\n".join(L)


def core(ctx: Ctx, dev: Device) -> str:
    p = ctx.plan
    up = p.link("DIST-CORESW")
    downs = [x for x in ctx.topo.devices if x.role in ("access", "server")]
    L = _hardening(ctx, dev.hostname)
    L += ["/interface bridge add name=BR-CORE vlan-filtering=no protocol-mode=rstp priority=0x1000 "
          f"pvid={BLACKHOLE_VLAN} frame-types=admit-only-vlan-tagged",
          "/interface ethernet set [find default-name=sfp28-1] comment=P2P-R-DIST",
          f"/ip address add address={up.b_ip}/30 interface=sfp28-1",
          f"/ipv6 address add address={up.b_ip6}/127 interface=sfp28-1 advertise=no"]
    for d in downs:
        port = f"sfp28-{ctx.access_index(d) + 1}"
        L.append(f"/interface bridge port add bridge=BR-CORE interface={port} "
                 f"pvid={BLACKHOLE_VLAN} frame-types=admit-only-vlan-tagged comment=TRUNK-{d.hostname}")
    for seg in ctx.core_segments:
        tagged = ["BR-CORE"] + [f"sfp28-{ctx.access_index(d) + 1}" for d in downs
                                if seg.vlan in ctx.trunk_vlans_for(d)]
        L += [f"/interface bridge vlan add bridge=BR-CORE vlan-ids={seg.vlan} tagged={','.join(tagged)}",
              f"/interface vlan add interface=BR-CORE name=vlan{seg.vlan}-{seg.tag[:12]} vlan-id={seg.vlan}",
              f"/ip address add address={seg.gateway}/{seg.prefix} interface=vlan{seg.vlan}-{seg.tag[:12]}",
              f"/ipv6 address add address={seg.ipv6_gateway}/64 interface=vlan{seg.vlan}-{seg.tag[:12]}"]
    for seg in ctx.dhcp_segments:
        name = f"vlan{seg.vlan}-{seg.tag[:12]}"
        L += [f"/ip pool add name=POOL-{seg.vlan} ranges={seg.dhcp_start}-{seg.dhcp_end}",
              f"/ip dhcp-server add name=DHCP-{seg.vlan} interface={name} address-pool=POOL-{seg.vlan} lease-time=8h",
              f"/ip dhcp-server network add address={prefix_str(seg.network)} gateway={seg.gateway} "
              f"dns-server={','.join(ctx.extras.dns_servers)} domain={ctx.extras.domain}"]
    L += ["/interface ethernet switch set 0 l3-hw-offloading=yes"]
    L += _ospf(ctx, dev.id, [prefix_str(up.network)], ["sfp28-1"],
               passive_v4=[prefix_str(s.network) for s in ctx.core_segments])
    svis = ",".join(f"vlan{s.vlan}-{s.tag[:12]}" for s in ctx.core_segments)
    L.append(f"/routing ospf interface-template add area=backbone-v3 interfaces={svis} passive=yes")
    L += ["# Activar al final para no perder acceso durante la carga:",
          "/interface bridge set BR-CORE vlan-filtering=yes"]
    return "\n".join(L)


def access(ctx: Ctx, dev: Device) -> str:
    p = ctx.plan
    mgmt, voice = p.segment("mgmt"), p.segment("voice")
    vlans = ctx.trunk_vlans_for(dev)
    L = _hardening(ctx, dev.hostname)
    L += [f"/interface bridge add name=BR-ACC vlan-filtering=no protocol-mode=rstp dhcp-snooping=yes "
          f"pvid={BLACKHOLE_VLAN}",
          "/interface bridge port add bridge=BR-ACC interface=sfp-sfpplus1 "
          "frame-types=admit-only-vlan-tagged trusted=yes comment=UPLINK-SW-CORE"]
    tagged: dict[int, list[str]] = {v: ["BR-ACC", "sfp-sfpplus1"] for v in vlans}
    for g in port_plan(ctx, dev):
        for port in range(g.start, g.end + 1):
            ifn = f"ether{port}"
            if g.kind == "unused":
                L += [f"/interface ethernet set [find default-name={ifn}] disabled=yes comment=NO-USADO"]
                continue
            if g.kind == "ap":
                L.append(f"/interface bridge port add bridge=BR-ACC interface={ifn} pvid={mgmt.vlan} "
                         f"edge=yes comment=ACCESS-POINT")
                tagged[p.segment("wifi").vlan].append(ifn)
                continue
            frame = "admit-all" if (g.kind == "user" and voice) else "admit-only-untagged-and-priority-tagged"
            L.append(f"/interface bridge port add bridge=BR-ACC interface={ifn} pvid={g.vlan} "
                     f"frame-types={frame} edge=yes bpdu-guard=yes comment={g.kind.upper()}")
            if g.kind == "user" and voice:
                tagged[voice.vlan].append(ifn)
    for v in vlans:
        L.append(f"/interface bridge vlan add bridge=BR-ACC vlan-ids={v} tagged={','.join(tagged[v])}")
    L += [f"/interface vlan add interface=BR-ACC name=vlan{mgmt.vlan}-MGMT vlan-id={mgmt.vlan}",
          f"/ip address add address={dev.mgmt_ip}/{mgmt.prefix} interface=vlan{mgmt.vlan}-MGMT",
          f"/ip route add dst-address=0.0.0.0/0 gateway={mgmt.gateway}",
          "# Activar al final para no perder acceso durante la carga:",
          "/interface bridge set BR-ACC vlan-filtering=yes"]
    return "\n".join(L)


PLATFORMS = {"edge": "CCR2004-16G-2S+", "dist": "CCR2004-16G-2S+", "core": "CRS518-16XS-2XQ",
             "access": "CRS354-48P-4S+2Q+", "server": "CRS354-48G-4S+2Q+"}
RENDER = {"edge": edge, "dist": dist, "core": core, "access": access, "server": access}
COMMENT = "#"
