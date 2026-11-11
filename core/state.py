"""
core/state.py
=============
Estado global de la aplicación (Módulo 1).

Un único objeto `ProjectConfig` vive en `st.session_state["config"]`. Todos los
módulos leen de él y el plan IP / topología / configuraciones se recalculan
automáticamente cuando cambia (memoizado por la huella de la configuración).

Este archivo NO importa streamlit a nivel de módulo para que el núcleo sea
testeable con pytest sin levantar la UI.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field

from . import validators as v

VENDORS = ("Cisco", "Huawei", "Fortinet", "MikroTik")
VPN_TYPES = ("IPsec", "SSL", "MPLS", "Ninguna")
SERVICES = ("VoIP", "CCTV", "Wi-Fi", "Servidores/DMZ")


@dataclass
class ProjectConfig:
    """Parámetros globales del escenario. Valores por defecto = edificio de 15 pisos."""

    project_name: str = "Torre Corporativa Bogotá"
    scenario: str = "Edificio corporativo"
    floors: int = 15
    hosts_total: int = 600
    budget_usd: int = 180_000
    isp_bandwidth_mbps: int = 500
    services: list[str] = field(default_factory=lambda: list(SERVICES))
    vpn_type: str = "IPsec"
    ipv4_base: str = "10.20.0.0/16"
    ipv6_base: str = "2001:db8:acad::/48"
    wan_block: str = "172.31.255.0/24"   # bloque dedicado a enlaces punto a punto /30
    isp_ipv4_link: str = "200.10.10.0/30"  # enlace con el ISP (lo entrega el proveedor)
    growth_pct: int = 25                 # reserva de crecimiento por piso
    cameras_per_floor: int = 4
    ap_per_floor: int = 3
    vendor: str = "Cisco"

    # ------------------------------------------------------------------ #
    def validate(self) -> list[str]:
        """Devuelve la lista de errores (vacía si todo es válido)."""
        errors: list[str] = []
        checks = [
            lambda: v.validate_project_name(self.project_name),
            lambda: v.validate_int_range(self.floors, 1, 60, "Número de pisos/zonas"),
            lambda: v.validate_int_range(self.hosts_total, 1, 20_000, "Hosts totales"),
            lambda: v.validate_int_range(self.budget_usd, 0, 50_000_000, "Presupuesto"),
            lambda: v.validate_int_range(self.isp_bandwidth_mbps, 1, 100_000, "Ancho de banda ISP"),
            lambda: v.validate_int_range(self.growth_pct, 0, 200, "Crecimiento"),
            lambda: v.validate_int_range(self.cameras_per_floor, 0, 64, "Cámaras por piso"),
            lambda: v.validate_int_range(self.ap_per_floor, 0, 32, "AP por piso"),
            lambda: v.validate_ipv4_network(self.ipv4_base, 8, 26),
            lambda: v.validate_ipv6_network(self.ipv6_base),
            lambda: v.validate_ipv4_network(self.wan_block, 8, 29),
        ]
        for check in checks:
            try:
                check()
            except v.ValidationError as exc:
                errors.append(str(exc))
        try:
            import ipaddress

            isp = ipaddress.IPv4Network(self.isp_ipv4_link, strict=True)
            if isp.prefixlen != 30:
                errors.append("El enlace con el ISP debe ser un /30.")
        except ValueError:
            errors.append(f"Enlace ISP inválido: '{self.isp_ipv4_link}'.")
        if self.vpn_type not in VPN_TYPES:
            errors.append("Tipo de VPN no soportado.")
        if self.vendor not in VENDORS:
            errors.append("Fabricante no soportado.")
        if any(s not in SERVICES for s in self.services):
            errors.append("Servicio no soportado.")
        return errors

    def fingerprint(self) -> str:
        """Huella estable para memoizar cálculos derivados."""
        raw = json.dumps(asdict(self), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    @property
    def hostname_prefix(self) -> str:
        """Prefijo corto para hostnames: el nombre si cabe en 12, si no sus iniciales.

        "Torre Corporativa Bogotá" → "TCB"; "Sede Norte" → "SEDE-NORTE".
        """
        slug = v.slugify_hostname(self.project_name, 40)
        if len(slug) <= 12:
            return slug
        return "".join(w[0] for w in slug.split("-") if w)[:6] or "NET"

    def has(self, service: str) -> bool:
        return service in self.services


# --------------------------------------------------------------------------- #
# Integración con Streamlit (import perezoso)
# --------------------------------------------------------------------------- #


def init_state() -> None:
    import streamlit as st

    st.session_state.setdefault("config", ProjectConfig())
    st.session_state.setdefault("console_history", [])
    st.session_state.setdefault("last_test_report", None)


def get_config() -> ProjectConfig:
    import streamlit as st

    init_state()
    return st.session_state["config"]


def set_config(cfg: ProjectConfig) -> None:
    import streamlit as st

    st.session_state["config"] = cfg
    # Invalida la caché derivada: los módulos 2–5 se recalculan solos.
    st.session_state.pop("_plan_cache", None)


def get_plan():
    """Devuelve (plan, topology) recalculando solo si la configuración cambió."""
    import streamlit as st

    from .ipam import build_address_plan
    from .topology import build_topology

    cfg = get_config()
    key = cfg.fingerprint()
    cache = st.session_state.get("_plan_cache")
    if cache and cache[0] == key:
        return cache[1], cache[2]
    plan = build_address_plan(cfg)
    topo = build_topology(cfg, plan)
    st.session_state["_plan_cache"] = (key, plan, topo)
    return plan, topo
