"""Módulo 4 — Generador de configuraciones multi-marca."""

from __future__ import annotations

import streamlit as st

from core.state import VENDORS, get_config, get_plan
from core.validators import ValidationError, validate_ipv4_host
from core.security_audit import audit, summary
from generators import Extras, bundle_zip, render_all
from generators.common import Ctx, device_summary
from ui.components import Stat, callout, hero, section, stat_grid

LANG = {"Cisco": "cisco", "Huawei": "bash", "Fortinet": "bash", "MikroTik": "bash"}


def get_extras() -> Extras:
    return st.session_state.get("extras", Extras())


def render() -> None:
    cfg = get_config()
    try:
        plan, topo = get_plan()
    except ValidationError as exc:
        callout(str(exc), "bad")
        return

    hero("Módulo 4 · Configuraciones", "Generador CLI multi-marca",
         "Plantillas listas para producción para Cisco IOS-XE, Huawei VRP, Fortinet FortiOS y MikroTik "
         "RouterOS v7: VLAN, interfaces, OSPFv2/v3, DHCP, NAT, QoS de voz, VPN y hardening.",
         f"VPN {cfg.vpn_type}", "ok")

    c1, c2 = st.columns([1, 2])
    vendor = c1.segmented_control("Fabricante", VENDORS, default=cfg.vendor, key="gen_vendor") or cfg.vendor
    with c2.expander("Parámetros del sitio remoto / proveedor (no secretos)",
                     expanded=cfg.vpn_type == "IPsec"):
        ex = get_extras()
        a, b = st.columns(2)
        peer = a.text_input("IP pública del peer VPN", "" if ex.peer_public_ip.startswith("<<") else ex.peer_public_ip,
                            placeholder="Ej. 190.85.10.20")
        rlan = b.text_input("LAN remota (CIDR)", "" if ex.remote_lan.startswith("<<") else ex.remote_lan,
                            placeholder="Ej. 10.50.0.0/16")
        if st.button("Aplicar parámetros"):
            try:
                new = Extras()
                if peer.strip():
                    new.peer_public_ip = str(validate_ipv4_host(peer))
                if rlan.strip():
                    new.remote_lan = rlan.strip()
                    if new.remote_lan_net is None:
                        raise ValidationError("LAN remota inválida (use formato CIDR sin bits de host).")
                st.session_state["extras"] = new
                st.rerun()
            except ValidationError as exc:
                st.error(str(exc))

    configs = render_all(cfg, plan, topo, vendor, get_extras())
    placeholders = sorted({p for c in configs for p in c.placeholders})
    secrets = [p for p in placeholders if any(k in p for k in ("SECRET", "PSK", "SNMPV3", "CERT", "USER"))]
    pending = [p for p in placeholders if p not in secrets]
    total_lines = sum(len(c.text.splitlines()) for c in configs)
    audits = {c.device_id: audit(c.text) for c in configs}
    risky = sum(1 for f in audits.values() for x in f if x.severity in ("alta", "media"))

    stat_grid([
        Stat("Archivos generados", str(len(configs)), f"uno por equipo · {vendor}"),
        Stat("Líneas de configuración", f"{total_lines:,}", "deterministas desde el plan IP"),
        Stat("Auditoría de seguridad", f"{risky} riesgos", "Telnet, credenciales por defecto, SNMP, ACL…",
             tone="ok" if not risky else "bad"),
        Stat("Parámetros pendientes", str(len(pending)),
             "complételos en el panel del sitio remoto" if pending else "ninguno",
             tone="warn" if pending else "ok"),
    ])
    callout(f"Los archivos nunca contienen contraseñas reales ({len(secrets)} secretos quedan como marcador): use su "
            "gestor de secretos o el .env local para reemplazar " + ", ".join(secrets) + " antes de aplicar.", "warn")

    section("Vista previa por equipo")
    roles = {"edge": "Borde", "dist": "Distribución", "core": "Núcleo", "access": "Acceso", "server": "Servidores",
             "router": "Router adicional"}
    labels = [f"{roles[c.role]} · {c.hostname}" for c in configs]
    idx = st.selectbox("Equipo", range(len(configs)), format_func=lambda i: labels[i])
    sel = configs[idx]
    dev = topo.get(sel.device_id)
    vlans, ips = device_summary(Ctx(cfg, plan, topo, get_extras()), dev)
    a, b, c = st.columns([1.1, 1.4, 2.5])
    a.markdown(f"**Hostname**  \n`{sel.hostname}`  \n\n**Plataforma**  \n{sel.vendor} {sel.platform}")
    b.markdown("**VLAN configuradas**  \n" + (", ".join(f"`{v}`" for v in vlans) if vlans else "— (equipo de capa 3)"))
    shown = ips[:6]
    c.markdown("**Direcciones IP**  \n" + "  \n".join(f"`{ip}` · {name}" for name, ip in shown)
               + (f"  \n… y {len(ips) - 6} más" if len(ips) > 6 else ""))
    findings = audits[sel.device_id]
    if findings:
        cnt = summary(findings)
        st.error(f"Auditoría: {cnt['alta']} riesgos altos, {cnt['media']} medios, {cnt['baja']} bajos en {sel.filename}.")
        st.dataframe([{"Severidad": f.severity, "Línea": f.line, "Problema": f.message, "Corrección": f.fix}
                      for f in findings], hide_index=True, width="stretch")
    else:
        st.success(f"Auditoría de seguridad sin hallazgos en {sel.filename}: solo SSH v2, sin credenciales por "
                   "defecto, SNMPv3 y acceso de gestión limitado a la VLAN 99.")
    st.caption(f"{sel.vendor} {sel.platform} · {len(sel.text.splitlines())} líneas · {sel.filename}")
    st.code(sel.text, language=LANG[vendor], line_numbers=True, height=520)

    c1, c2 = st.columns(2)
    c1.download_button(f"Descargar {sel.filename}", sel.text.encode("utf-8"), sel.filename, "text/plain",
                       width="stretch")
    c2.download_button(f"Descargar todos ({len(configs)} .txt en .zip)", bundle_zip(configs),
                       f"configs_{vendor.lower()}_{cfg.hostname_prefix}.zip", "application/zip",
                       type="primary", width="stretch")
