"""Módulo 1 — Requerimientos, escenario y parámetros globales."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.capacity import bandwidth_demand_mbps, bill_of_materials, total_cost
from core.state import SERVICES, VENDORS, VPN_TYPES, ProjectConfig, get_config, get_plan, set_config
from core.validators import ValidationError
from ui.components import Stat, callout, hero, section, stat_grid

PRESETS = {
    "Edificio corporativo (15 pisos)": dict(scenario="Edificio corporativo", floors=15, hosts_total=600,
                                            budget_usd=180_000, isp_bandwidth_mbps=500),
    "Sede regional (3 zonas)": dict(scenario="Sede regional", floors=3, hosts_total=120,
                                    budget_usd=45_000, isp_bandwidth_mbps=200),
    "Campus universitario (8 bloques)": dict(scenario="Campus", floors=8, hosts_total=1600,
                                             budget_usd=350_000, isp_bandwidth_mbps=2000),
    "Sucursal pequeña (1 piso)": dict(scenario="Sucursal", floors=1, hosts_total=25,
                                      budget_usd=8_000, isp_bandwidth_mbps=100),
}


def render() -> None:
    cfg = get_config()
    hero("Módulo 1 · Requerimientos", "Escenario y parámetros globales",
         "Todo lo que defina aquí se sincroniza en el estado global y recalcula automáticamente "
         "el plan IP, la topología, las configuraciones y la consola.",
         f"Diseño {cfg.fingerprint()}", "ok")

    c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
    preset = c1.selectbox("Plantilla de escenario", ["— Personalizado —", *PRESETS])
    if c2.button("Aplicar plantilla", width="stretch", disabled=preset not in PRESETS):
        data = {**cfg.__dict__, **PRESETS[preset]}
        set_config(ProjectConfig(**data))
        st.rerun()

    with st.form("requirements", border=False):
        section("Proyecto")
        a, b, c = st.columns(3)
        name = a.text_input("Nombre del proyecto", cfg.project_name, max_chars=48)
        scenario = b.text_input("Tipo de escenario", cfg.scenario, max_chars=40)
        vendor = c.selectbox("Fabricante principal", VENDORS, index=VENDORS.index(cfg.vendor))

        section("Dimensionamiento")
        a, b, c, d = st.columns(4)
        floors = a.number_input("Pisos / zonas", 1, 60, cfg.floors)
        hosts = b.number_input("Clientes / hosts totales", 1, 20_000, cfg.hosts_total, step=10)
        growth = c.number_input("Crecimiento previsto (%)", 0, 200, cfg.growth_pct, step=5)
        budget = d.number_input("Presupuesto (USD)", 0, 50_000_000, cfg.budget_usd, step=1000)
        a, b, c, d = st.columns(4)
        isp_bw = a.number_input("Ancho de banda ISP (Mbps)", 1, 100_000, cfg.isp_bandwidth_mbps, step=50)
        cams = b.number_input("Cámaras por piso", 0, 64, cfg.cameras_per_floor)
        aps = c.number_input("Access Points por piso", 0, 32, cfg.ap_per_floor)
        vpn = d.selectbox("Tipo de VPN", VPN_TYPES, index=VPN_TYPES.index(cfg.vpn_type))
        services = st.multiselect("Servicios", SERVICES, default=cfg.services)

        section("Direccionamiento base")
        a, b, c, d = st.columns(4)
        v4 = a.text_input("Red base IPv4 (CIDR)", cfg.ipv4_base, help="Privada RFC 1918, p. ej. 10.20.0.0/16")
        v6 = b.text_input("Red base IPv6 (CIDR)", cfg.ipv6_base, help="Ej. 2001:db8:acad::/48")
        wan = c.text_input("Bloque WAN para /30", cfg.wan_block)
        isp = d.text_input("Enlace ISP (/30 del proveedor)", cfg.isp_ipv4_link)

        submitted = st.form_submit_button("Guardar y recalcular", type="primary")

    if submitted:
        candidate = ProjectConfig(
            project_name=name.strip(), scenario=scenario.strip() or "Escenario", floors=int(floors),
            hosts_total=int(hosts), budget_usd=int(budget), isp_bandwidth_mbps=int(isp_bw),
            services=list(services), vpn_type=vpn, ipv4_base=v4.strip(), ipv6_base=v6.strip(),
            wan_block=wan.strip(), isp_ipv4_link=isp.strip(), growth_pct=int(growth),
            cameras_per_floor=int(cams), ap_per_floor=int(aps), vendor=vendor)
        errors = candidate.validate()
        if not errors:
            try:  # validación profunda: ¿cabe el diseño en la red base?
                from core.ipam import build_address_plan
                build_address_plan(candidate)
            except ValidationError as exc:
                errors = [str(exc)]
        if errors:
            for e in errors:
                st.error(e)
        else:
            set_config(candidate)
            st.toast("Diseño actualizado en todos los módulos", icon="✅")
            st.rerun()

    _summary()


def _summary() -> None:
    cfg = get_config()
    try:
        plan, topo = get_plan()
    except ValidationError as exc:
        callout(str(exc), "bad")
        return
    bom = bill_of_materials(cfg, topo)
    cost = total_cost(bom)
    demand = bandwidth_demand_mbps(cfg)
    need = sum(demand.values())
    budget_pct = 100 * cost / cfg.budget_usd if cfg.budget_usd else 100
    bw_pct = 100 * need / cfg.isp_bandwidth_mbps

    section("Viabilidad del diseño")
    stat_grid([
        Stat("Segmentos / VLAN", str(len(plan.segments)), f"{cfg.floors} pisos + servicios"),
        Stat("Equipos de red", str(sum(1 for d in topo.devices if d.role not in ('isp', 'remote', 'dmz'))),
             f"{topo.counts.get('access', 0)} switches de acceso"),
        Stat("Costo estimado", f"US$ {cost:,.0f}", f"{budget_pct:.0f} % del presupuesto",
             budget_pct, "ok" if budget_pct <= 85 else "warn" if budget_pct <= 100 else "bad"),
        Stat("Demanda WAN pico", f"{need:,.0f} Mbps", f"{bw_pct:.0f} % del enlace ISP",
             bw_pct, "ok" if bw_pct <= 70 else "warn" if bw_pct <= 100 else "bad"),
    ])
    if budget_pct > 100:
        callout(f"El costo referencial supera el presupuesto en US$ {cost - cfg.budget_usd:,.0f}. "
                "Considere otro fabricante o reducir el crecimiento.", "bad")
    if bw_pct > 70:
        callout("La demanda pico supera el 70 % del enlace: se recomienda ampliar el ISP o un segundo enlace.",
                "warn")

    left, right = st.columns([3, 2])
    with left:
        section(f"Lista de materiales referencial · {cfg.vendor}")
        st.dataframe(pd.DataFrame([{"Ítem": l.item, "Cant.": l.qty, "Unitario (USD)": l.unit,
                                    "Subtotal (USD)": l.total} for l in bom]),
                     hide_index=True, width="stretch")
        st.caption("Precios referenciales editables en core/capacity.py; reemplácelos por cotizaciones reales.")
    with right:
        section("Demanda de ancho de banda (Mbps)")
        st.bar_chart(pd.Series(demand, name="Mbps"), horizontal=True, color="#ef233c", height=230)
