"""Módulo 2 — Planificación IP matemática estricta (IPv4 / IPv6)."""

from __future__ import annotations

import ipaddress

import pandas as pd
import streamlit as st

from core.ipam import links_to_rows, plan_to_rows
from core.state import get_config, get_plan
from core.validators import ValidationError
from ui.components import Stat, callout, hero, section, stat_grid


def render() -> None:
    cfg = get_config()
    try:
        plan, _ = get_plan()
    except ValidationError as exc:
        hero("Módulo 2 · IPAM", "Planificación IP", "No se pudo calcular el plan.", "Error", "bad")
        callout(str(exc), "bad")
        return

    hero("Módulo 2 · IPAM", "Planificación IP IPv4 / IPv6",
         "VLSM de mayor a menor con la librería estándar ipaddress, gateways en la primera IP útil "
         "y enlaces WAN /30 sin desperdicio, igual que en Cisco Packet Tracer.",
         f"{plan.base_v4} · {plan.base_v6}", "ok")

    stat_grid([
        Stat("Hosts requeridos", f"{plan.required_hosts:,}", f"con {cfg.growth_pct} % de crecimiento"),
        Stat("IPs útiles asignadas", f"{plan.usable_allocated:,}", f"eficiencia VLSM {plan.efficiency} %",
             plan.efficiency, "ok" if plan.efficiency >= 60 else "warn"),
        Stat("Uso de la red base", f"{plan.base_usage} %", f"{plan.allocated_addresses:,} de "
             f"{plan.base_v4.num_addresses:,} direcciones", plan.base_usage),
        Stat("Ruta sumarizada", str(plan.summary_route), "anunciada por OSPF hacia el borde"),
    ])

    tab_lan, tab_wan, tab_calc = st.tabs(["Subredes LAN / VLAN", "Enlaces WAN punto a punto", "Calculadora"])
    with tab_lan:
        df = pd.DataFrame(plan_to_rows(plan))
        st.dataframe(df, hide_index=True, width="stretch", height=min(38 * (len(df) + 1), 640),
                     column_config={"Uso %": st.column_config.ProgressColumn("Uso %", min_value=0,
                                                                             max_value=100, format="%.0f%%")})
        c1, c2 = st.columns(2)
        c1.download_button("Descargar plan IP (CSV)", df.to_csv(index=False).encode("utf-8-sig"),
                           f"plan_ip_{cfg.hostname_prefix}.csv", "text/csv", width="stretch")
        c2.download_button("Descargar plan IP (Markdown)", _to_markdown(df).encode("utf-8"),
                           f"plan_ip_{cfg.hostname_prefix}.md", "text/markdown", width="stretch")
    with tab_wan:
        callout("Cada enlace usa un /30: 4 direcciones = red + 2 hosts útiles + broadcast. El lado A "
                "(upstream) toma la 1.ª IP útil y el lado B la 2.ª. En IPv6 se usa /127 (RFC 6164).")
        st.dataframe(pd.DataFrame(links_to_rows(plan)), hide_index=True, width="stretch")
    with tab_calc:
        _calculator()


def _to_markdown(df: pd.DataFrame) -> str:
    """Tabla Markdown sin dependencias externas (para pegar en el informe)."""
    head = "| " + " | ".join(df.columns) + " |"
    sep = "|" + "|".join("---" for _ in df.columns) + "|"
    body = ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join([head, sep, *body]) + "\n"


def _calculator() -> None:
    section("Calculadora de subred (verificación manual)")
    value = st.text_input("Dirección con prefijo", "192.168.10.77/26", key="calc_in")
    try:
        iface = ipaddress.ip_interface(value.strip())
    except ValueError:
        st.error("Formato inválido. Ejemplo: 192.168.10.77/26 o 2001:db8::5/64")
        return
    net = iface.network
    if net.version == 4:
        hosts = max(net.num_addresses - 2, 0) if net.prefixlen < 31 else net.num_addresses
        rows = {
            "Red": str(net.network_address), "Máscara": str(net.netmask), "Wildcard": str(net.hostmask),
            "Primera útil (gateway)": str(net.network_address + 1) if net.prefixlen < 31 else "—",
            "Última útil": str(net.broadcast_address - 1) if net.prefixlen < 31 else "—",
            "Broadcast": str(net.broadcast_address) if net.prefixlen < 31 else "—",
            "Hosts útiles": f"{hosts:,}", "Clase de bloque": "Privada" if net.is_private else "Pública",
            "Binario máscara": ".".join(f"{int(o):08b}" for o in str(net.netmask).split(".")),
        }
    else:
        rows = {"Red": str(net.network_address), "Prefijo": f"/{net.prefixlen}",
                "Direcciones": f"{net.num_addresses:,}", "Primera": str(net.network_address),
                "Última": str(net.broadcast_address), "Expandida": net.network_address.exploded}
    st.dataframe(pd.DataFrame(rows.items(), columns=["Campo", "Valor"]), hide_index=True,
                 width="stretch")
