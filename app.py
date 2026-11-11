"""
RED-LION-INTERCONNECTION
========================
Punto de entrada de la aplicación Streamlit.

    streamlit run app.py

Arquitectura (ver docs/arquitectura.md):
    core/        → lógica pura y testeable (estado, IPAM, topología, validadores, calidad)
    generators/  → motores de plantillas CLI por fabricante
    netdevops/   → transporte SSH/Telnet y simulador de laboratorio
    ui/          → sistema de diseño y componentes
    views/       → una vista por módulo (M1–M6)
"""

from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv

load_dotenv()  # Las credenciales SOLO se leen de .env (excluido por .gitignore)

st.set_page_config(page_title="RED-LION-INTERCONNECTION", page_icon="🦁", layout="wide",
                   initial_sidebar_state="expanded")

from core.state import get_config, get_plan, init_state  # noqa: E402
from core.validators import ValidationError  # noqa: E402
from ui.components import brand, inject_css  # noqa: E402
from views import (m1_requirements, m2_ipam, m3_topology, m4_configs, m5_console,  # noqa: E402
                   m6_security)

MODULES = {
    "01  Requerimientos": m1_requirements,
    "02  Planificación IP": m2_ipam,
    "03  Topología": m3_topology,
    "04  Configuraciones": m4_configs,
    "05  Conexión y despliegue": m5_console,
    "06  Ciberdefensa y pruebas": m6_security,
}


def sidebar() -> str:
    with st.sidebar:
        brand()
        choice = st.radio("Módulos", list(MODULES), label_visibility="collapsed", key="nav")
        cfg = get_config()
        st.divider()
        try:
            plan, topo = get_plan()
            st.caption("DISEÑO ACTIVO")
            st.markdown(
                f"**{cfg.project_name}**  \n"
                f"{cfg.floors} pisos · {cfg.hosts_total:,} hosts · {cfg.vendor}  \n"
                f"`{plan.base_v4}` · `{plan.summary_route}`  \n"
                f"{len(plan.segments)} VLAN · {len(topo.devices)} nodos · VPN {cfg.vpn_type}"
            )
        except ValidationError as exc:
            st.error(f"Diseño inválido: {exc}")
        st.caption("v1.0 · Python · Streamlit · paramiko")
    return choice


def main() -> None:
    inject_css()
    init_state()
    choice = sidebar()
    MODULES[choice].render()


main()
