"""
generators/fortinet.py — Fortinet FortiOS 7.4 / FortiSwitchOS 7.4
Plataformas de referencia: FortiGate 200F (borde, NGFW + VPN),
FortiGate 100F (distribución / ISFW), FortiSwitch 1048E (núcleo L3),
FortiSwitch 448E-FPOE (acceso).

Nota de diseño: Fortinet no fabrica routers clásicos; en este perfil el
borde y la distribución son FortiGate (firewall de segmentación interna).
FortiGate niega todo por defecto, por eso se generan políticas explícitas.
"""

from __future__ import annotations

from core.topology import Device

from .common import BLACKHOLE_VLAN, LOCAL_AS, PROVIDER_AS, TRANSIT_VLAN, Ctx, port_plan

VENDOR = "Fortinet"


def _global(ctx: Ctx, hostname: str, fortigate: bool = True) -> list[str]:
    mgmt = ctx.plan.segment("mgmt")
    L = ["config system global",
         f'    set hostname "{hostname}"',
         "    set admintimeout 10",
         "    set admin-lockout-threshold 3",
         "    set admin-lockout-duration 300"]
    if fortigate:
        L += ["    set admin-https-redirect enable", "    set strong-crypto enable",
              "    set admin-telnet disable"]
    L += ["end",
          "config system admin",
          '    edit "netadmin"',
          '        set accprofile "super_admin"',
          f"        set trusthost1 {mgmt.network.network_address} {mgmt.mask}",
          '        set password "<<ADMIN_SECRET>>"',
          "    next",
          "end",
          "config system ntp",
          "    set ntpsync enable",
          "    set type custom",
          "    config ntpserver",
          f'        edit 1\n            set server "{ctx.extras.ntp_server}"\n        next',
          "    end",
          "end",
          "config system snmp user",
          '    edit "netops"',
          "        set security-level auth-priv",
          "        set auth-proto sha256",
          '        set auth-pwd "<<SNMPV3_AUTH>>"',
          "        set priv-proto aes256",
          '        set priv-pwd "<<SNMPV3_PRIV>>"',
          "    next",
          "end"]
    return L


def _iface(name: str, ip: str, mask: str, role: str, access: str, alias: str,
           ip6: str | None = None, extra: list[str] = ()) -> list[str]:
    L = [f'    edit "{name}"', f'        set alias "{alias}"', f"        set ip {ip} {mask}",
         f"        set allowaccess {access}", f"        set role {role}"]
    L += [f"        {x}" for x in extra]
    if ip6:
        L += ["        config ipv6", f"            set ip6-address {ip6}",
              f"            set ip6-allowaccess {access.replace('https', '').strip() or 'ping'}",
              "        end"]
    L.append("    next")
    return L


def _ospf(ctx: Ctx, dev_id: str, prefixes: list[tuple[str, str]], originate: bool = False) -> list[str]:
    L = ["config router ospf", f"    set router-id {ctx.router_id(dev_id)}"]
    if originate:
        L.append("    set default-information-originate always")
    L += ["    config area", '        edit 0.0.0.0', "        next", "    end", "    config network"]
    for i, (net, mask) in enumerate(prefixes, start=1):
        L += [f"        edit {i}", f"            set prefix {net} {mask}", "        next"]
    L += ["    end", "end",
          "config router ospf6", f"    set router-id {ctx.router_id(dev_id)}",
          "    config area", "        edit 0.0.0.0", "        next", "    end", "end"]
    return L


def _policy(pid: int, name: str, src: str, dst: str, saddr: str, daddr: str, service: str = "ALL",
            nat: bool = False, utm: bool = True) -> list[str]:
    L = [f"    edit {pid}", f'        set name "{name}"', f'        set srcintf "{src}"',
         f'        set dstintf "{dst}"', f'        set srcaddr "{saddr}"', f'        set dstaddr "{daddr}"',
         "        set action accept", '        set schedule "always"', f'        set service "{service}"',
         "        set logtraffic all"]
    if utm:
        L += ["        set utm-status enable", '        set ssl-ssh-profile "certificate-inspection"',
              '        set av-profile "default"', '        set webfilter-profile "default"',
              '        set ips-sensor "default"', '        set application-list "default"']
    if nat:
        L.append("        set nat enable")
    L.append("    next")
    return L


def edge(ctx: Ctx, dev: Device) -> str:
    p, cfg = ctx.plan, ctx.cfg
    isp, down, dmz, summ = p.link("ISP-EDGE"), p.link("EDGE-DIST"), p.segment("dmz"), p.summary_route
    L = _global(ctx, dev.hostname)
    L += ["config system interface"]
    L += _iface("wan1", str(isp.b_ip), isp.mask, "wan", "ping", "WAN-ISP", f"{isp.b_ip6}/127",
                [f"set estimated-upstream-bandwidth {cfg.isp_bandwidth_mbps * 1000}",
                 f"set estimated-downstream-bandwidth {cfg.isp_bandwidth_mbps * 1000}"])
    L += _iface("port2", str(down.a_ip), down.mask, "lan", "ping ssh https", "P2P-R-DIST", f"{down.a_ip6}/127")
    if dmz:
        L += _iface("dmz", str(dmz.gateway), dmz.mask, "dmz", "ping", "DMZ", f"{dmz.ipv6_gateway}/64")
    L += ["end"]

    L += ["config firewall address",
          f'    edit "LAN-CORP"\n        set subnet {summ.network_address} {summ.netmask}\n    next']
    if dmz:
        L.append(f'    edit "NET-DMZ"\n        set subnet {dmz.network.network_address} {dmz.mask}\n    next')
    rnet, rmask, _ = ctx.extras.remote_lan_parts()
    if cfg.vpn_type == "IPsec":
        L.append(f'    edit "LAN-REMOTA"\n        set subnet {rnet} {rmask}\n    next')
    L += ["end"]

    L += ["config router static",
          f"    edit 1\n        set gateway {isp.a_ip}\n        set device \"wan1\"\n        set comment \"DEFAULT-ISP\"\n    next",
          "end",
          "config router static6",
          f"    edit 1\n        set gateway {isp.a_ip6}\n        set device \"wan1\"\n    next",
          "end"]

    # VPN ------------------------------------------------------------------
    peer = ctx.extras.peer_public_ip
    if cfg.vpn_type == "IPsec" and p.tunnel:
        t = p.tunnel
        L += ["config vpn ipsec phase1-interface", '    edit "VPN-REMOTO"', '        set interface "wan1"',
              "        set ike-version 2", "        set peertype any", "        set net-device disable",
              "        set proposal aes256gcm-prfsha384 aes256-sha256", "        set dhgrp 20 19",
              f"        set remote-gw {peer}", '        set psksecret "<<VPN_PSK>>"',
              "        set dpd on-idle", "    next", "end",
              "config vpn ipsec phase2-interface", '    edit "VPN-REMOTO-P2"',
              '        set phase1name "VPN-REMOTO"', "        set proposal aes256gcm",
              "        set pfs enable", "        set dhgrp 20", "        set auto-negotiate enable",
              "    next", "end",
              "config system interface", '    edit "VPN-REMOTO"',
              f"        set ip {t.a_ip} 255.255.255.255", f"        set remote-ip {t.b_ip} {t.mask}",
              "        set allowaccess ping", "    next", "end",
              "config router static",
              f'    edit 2\n        set dstaddr "LAN-REMOTA"\n        set device "VPN-REMOTO"\n    next',
              f'    edit 3\n        set dstaddr "LAN-REMOTA"\n        set blackhole enable\n        set distance 254\n    next',
              "end"]
    elif cfg.vpn_type == "SSL":
        L += ["config user group", '    edit "VPN-USERS"',
              '        set member "<<VPN_USER_OR_LDAP_GROUP>>"', "    next", "end",
              "config firewall address",
              '    edit "SSLVPN_TUNNEL_ADDR1"\n        set type iprange\n        set start-ip 10.212.134.200\n        set end-ip 10.212.134.210\n    next',
              "end",
              "config vpn ssl web portal", '    edit "full-access"', "        set tunnel-mode enable",
              '        set ip-pools "SSLVPN_TUNNEL_ADDR1"', "        set split-tunneling enable",
              '        set split-tunneling-routing-address "LAN-CORP"', "    next", "end",
              "config vpn ssl settings", '    set servercert "Fortinet_Factory"',
              '    set tunnel-ip-pools "SSLVPN_TUNNEL_ADDR1"', '    set source-interface "wan1"',
              '    set source-address "all"', '    set default-portal "full-access"',
              "    set port 10443", "    set login-attempt-limit 3", "    set login-block-time 300",
              "end"]
    elif cfg.vpn_type == "MPLS" and p.tunnel:
        t = p.tunnel
        L += ["config system interface"]
        L += _iface("port3", str(t.a_ip), t.mask, "wan", "ping", "CE-PE-MPLS")
        L += ["end", "config router bgp", f"    set as {LOCAL_AS}", f"    set router-id {ctx.router_id(dev.id)}",
              "    config neighbor", f'        edit "{t.b_ip}"', f"            set remote-as {PROVIDER_AS}",
              "        next", "    end", "    config network",
              f"        edit 1\n            set prefix {summ.network_address} {summ.netmask}\n        next",
              "    end", "end"]

    # Políticas ------------------------------------------------------------
    L += ["config firewall policy"]
    L += _policy(1, "LAN-a-INTERNET", "port2", "wan1", "LAN-CORP", "all", nat=True)
    pid = 2
    if dmz:
        L += _policy(pid, "DMZ-a-INTERNET", "dmz", "wan1", "NET-DMZ", "all", nat=True); pid += 1
        L += _policy(pid, "LAN-a-DMZ", "port2", "dmz", "LAN-CORP", "NET-DMZ", "HTTPS"); pid += 1
    if cfg.vpn_type == "IPsec":
        L += _policy(pid, "LAN-a-VPN", "port2", "VPN-REMOTO", "LAN-CORP", "LAN-REMOTA", utm=False); pid += 1
        L += _policy(pid, "VPN-a-LAN", "VPN-REMOTO", "port2", "LAN-REMOTA", "LAN-CORP", utm=False); pid += 1
    if cfg.vpn_type == "SSL":
        L += [f"    edit {pid}", '        set name "SSLVPN-a-LAN"', '        set srcintf "ssl.root"',
              '        set dstintf "port2"', '        set srcaddr "SSLVPN_TUNNEL_ADDR1"',
              '        set dstaddr "LAN-CORP"', '        set groups "VPN-USERS"', "        set action accept",
              '        set schedule "always"', '        set service "ALL"', "    next"]
    L += ["end"]

    if cfg.has("VoIP"):
        L += ["config firewall shaper traffic-shaper", '    edit "VOZ-PRIORIDAD"',
              f"        set guaranteed-bandwidth {int(cfg.isp_bandwidth_mbps * 1000 * 0.3)}",
              "        set priority high", "        set diffserv enable",
              "        set diffservcode 101110", "    next", "end",
              "config firewall shaping-policy", "    edit 1", '        set name "QOS-VOZ"',
              '        set service "SIP" "H323"', '        set dstintf "wan1"',
              '        set traffic-shaper "VOZ-PRIORIDAD"', '        set srcaddr "LAN-CORP"',
              '        set dstaddr "all"', "    next", "end"]

    prefixes = [(str(down.network.network_address), down.mask)]
    L += _ospf(ctx, dev.id, prefixes, originate=True)
    return "\n".join(L)


def dist(ctx: Ctx, dev: Device) -> str:
    p = ctx.plan
    up, down, summ = p.link("EDGE-DIST"), p.link("DIST-CORESW"), p.summary_route
    L = _global(ctx, dev.hostname)
    L += ["config system interface"]
    L += _iface("port1", str(up.b_ip), up.mask, "wan", "ping", "P2P-R-CORE", f"{up.b_ip6}/127")
    L += _iface("port2", str(down.a_ip), down.mask, "lan", "ping ssh https", "P2P-SW-CORE", f"{down.a_ip6}/127")
    L += ["end",
          "config firewall address",
          f'    edit "LAN-CORP"\n        set subnet {summ.network_address} {summ.netmask}\n    next',
          "end",
          "config firewall policy"]
    L += _policy(1, "LAN-a-BORDE", "port2", "port1", "LAN-CORP", "all")
    L += _policy(2, "BORDE-a-LAN", "port1", "port2", "all", "LAN-CORP", utm=True)
    L += ["end"]
    L += _ospf(ctx, dev.id, [(str(up.network.network_address), up.mask),
                             (str(down.network.network_address), down.mask)])
    return "\n".join(L)


def _fsw_global(ctx: Ctx, hostname: str) -> list[str]:
    return _global(ctx, hostname, fortigate=False) + [
        "config switch stp settings", "    set status enable", "end"]


def core(ctx: Ctx, dev: Device) -> str:
    p = ctx.plan
    up = p.link("DIST-CORESW")
    L = _fsw_global(ctx, dev.hostname)
    L += ["config switch stp instance", '    edit "0"', "        set priority 4096", "    next", "end",
          "config switch vlan"]
    for seg in ctx.core_segments:
        L += [f"    edit {seg.vlan}", f'        set description "{seg.tag}"', "    next"]
    L += [f"    edit {TRANSIT_VLAN}", '        set description "TRANSITO-R-DIST"', "    next",
          f"    edit {BLACKHOLE_VLAN}", '        set description "BLACKHOLE"', "    next", "end"]

    L += ["config system interface",
          f'    edit "vlan{TRANSIT_VLAN}"', f"        set ip {up.b_ip} {up.mask}",
          "        set allowaccess ping", f"        set vlanid {TRANSIT_VLAN}",
          '        set interface "internal"', "    next"]
    for seg in ctx.core_segments:
        L += [f'    edit "vlan{seg.vlan}"', f'        set description "GW-{seg.tag}"',
              f"        set ip {seg.gateway} {seg.mask}",
              f"        set allowaccess {'ping ssh https' if seg.role == 'mgmt' else 'ping'}",
              f"        set vlanid {seg.vlan}", '        set interface "internal"',
              "        config ipv6", f"            set ip6-address {seg.ipv6_gateway}/64",
              "        end", "    next"]
    L += ["end", "config switch interface",
          '    edit "port52"', '        set description "UPLINK-R-DIST"',
          f"        set native-vlan {TRANSIT_VLAN}", "        set allowed-vlans-all disable",
          "    next"]
    for d in [x for x in ctx.topo.devices if x.role in ("access", "server")]:
        L += [f'    edit "port{ctx.access_index(d)}"', f'        set description "TRUNK-{d.hostname}"',
              f"        set native-vlan {BLACKHOLE_VLAN}",
              f"        set allowed-vlans {','.join(map(str, ctx.trunk_vlans_for(d)))}",
              "        set dhcp-snooping trusted", "    next"]
    L += ["end"]

    L += ["config system dhcp server"]
    for i, seg in enumerate(ctx.dhcp_segments, start=1):
        L += [f"    edit {i}", f'        set interface "vlan{seg.vlan}"',
              f"        set default-gateway {seg.gateway}", f"        set netmask {seg.mask}",
              f"        set dns-server1 {ctx.extras.dns_servers[0]}",
              f"        set dns-server2 {ctx.extras.dns_servers[-1]}",
              f'        set domain "{ctx.extras.domain}"', "        set lease-time 28800",
              "        config ip-range",
              f"            edit 1\n                set start-ip {seg.dhcp_start}\n                set end-ip {seg.dhcp_end}\n            next",
              "        end", "    next"]
    L += ["end"]

    prefixes = [(str(up.network.network_address), up.mask)]
    prefixes += [(str(s.network.network_address), s.mask) for s in ctx.core_segments]
    L += _ospf(ctx, dev.id, prefixes)
    return "\n".join(L)


def access(ctx: Ctx, dev: Device) -> str:
    p = ctx.plan
    mgmt, voice = p.segment("mgmt"), p.segment("voice")
    vlans = ctx.trunk_vlans_for(dev)
    by_vlan = {s.vlan: s for s in p.segments}
    L = _fsw_global(ctx, dev.hostname)
    L += ["config switch vlan"]
    for v in vlans:
        extra = ["        set dhcp-snooping enable"]
        L += [f"    edit {v}", f'        set description "{by_vlan[v].tag}"'] + extra + ["    next"]
    L += [f"    edit {BLACKHOLE_VLAN}", '        set description "BLACKHOLE"', "    next", "end",
          "config system interface", f'    edit "vlan{mgmt.vlan}"',
          f"        set ip {dev.mgmt_ip} {mgmt.mask}", "        set allowaccess ping ssh https",
          f"        set vlanid {mgmt.vlan}", '        set interface "internal"', "    next", "end",
          "config router static", f"    edit 1\n        set gateway {mgmt.gateway}\n        set device \"vlan{mgmt.vlan}\"\n    next",
          "end", "config switch interface"]
    for g in port_plan(ctx, dev):
        for port in range(g.start, g.end + 1):
            L += [f'    edit "port{port}"']
            if g.kind in ("user", "server"):
                L += [f'        set description "{"USUARIO" if g.kind == "user" else "SERVIDOR"}"',
                      f"        set native-vlan {g.vlan}"]
                if g.kind == "user" and voice:
                    L += [f"        set allowed-vlans {voice.vlan}"]
                L += ["        set edge-port enabled", "        set stp-bpdu-guard enabled",
                      "        set learning-limit 3"]
            elif g.kind == "camera":
                L += ['        set description "CAMARA"', f"        set native-vlan {g.vlan}",
                      "        set edge-port enabled", "        set stp-bpdu-guard enabled"]
            elif g.kind == "ap":
                wifi = p.segment("wifi")
                L += ['        set description "ACCESS-POINT"', f"        set native-vlan {mgmt.vlan}",
                      f"        set allowed-vlans {wifi.vlan}", "        set edge-port enabled"]
            else:
                L += ['        set description "NO-USADO"', f"        set native-vlan {BLACKHOLE_VLAN}"]
            L.append("    next")
    L += ['    edit "port49"', '        set description "UPLINK-SW-CORE"',
          f"        set native-vlan {BLACKHOLE_VLAN}",
          f"        set allowed-vlans {','.join(map(str, vlans))}",
          "        set dhcp-snooping trusted", "    next", "end"]
    # Puertos no usados: apagado administrativo
    unused = [g for g in port_plan(ctx, dev) if g.kind == "unused"]
    if unused:
        L += ["config switch physical-port"]
        for g in unused:
            for port in range(g.start, g.end + 1):
                L += [f'    edit "port{port}"', "        set status down", "    next"]
        L += ["end"]
    return "\n".join(L)


PLATFORMS = {"edge": "FortiGate 200F", "dist": "FortiGate 100F", "core": "FortiSwitch 1048E",
             "access": "FortiSwitch 448E-FPOE", "server": "FortiSwitch 448E"}
RENDER = {"edge": edge, "dist": dist, "core": core, "access": access, "server": access}
COMMENT = "#"
