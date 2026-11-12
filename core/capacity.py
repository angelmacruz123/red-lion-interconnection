"""
core/capacity.py
================
Estimaciones del Módulo 1: lista de equipos (BOM), costo frente al
presupuesto y demanda de ancho de banda frente al enlace del ISP.

Los precios son REFERENCIALES (USD, lista aproximada, sin licencias de
soporte ni impuestos) y están en un solo diccionario para que el equipo
los actualice con cotizaciones reales. No pretenden ser precios oficiales.
"""

from __future__ import annotations

from dataclasses import dataclass

from .state import ProjectConfig
from .topology import Topology

UNIT_PRICE_USD = {
    #            borde   distrib.  núcleo   acceso  servidores  AP     cámara
    "Cisco":    {"edge": 6500, "dist": 4800, "core": 14000, "access": 4200, "server": 3200, "ap": 900, "cam": 450},
    "Huawei":   {"edge": 4200, "dist": 3100, "core": 9500,  "access": 2600, "server": 2100, "ap": 600, "cam": 350},
    "Fortinet": {"edge": 9800, "dist": 5200, "core": 11500, "access": 3300, "server": 2600, "ap": 750, "cam": 400},
    "MikroTik": {"edge": 800,  "dist": 800,  "core": 1600,  "access": 650,  "server": 450,  "ap": 180, "cam": 300},
}

# Perfil de tráfico por servicio (Mbps). Valores de diseño conservadores.
KBPS_PER_USER_DATA = 1500       # navegación + SaaS en hora pico
VOIP_KBPS_PER_CALL = 100        # G.711 con overhead IP/UDP/RTP
VOIP_CONCURRENCY = 0.25         # 25 % de extensiones hablando a la vez (Erlang simplificado)
CCTV_MBPS_PER_CAM_UPLINK = 0.5  # solo cámaras visualizadas de forma remota
WIFI_FACTOR = 0.3               # tráfico adicional de invitados/BYOD


@dataclass
class BomLine:
    item: str
    qty: int
    unit: int

    @property
    def total(self) -> int:
        return self.qty * self.unit


def bill_of_materials(cfg: ProjectConfig, topo: Topology, vendor: str | None = None) -> list[BomLine]:
    vendor = vendor or cfg.vendor
    price = UNIT_PRICE_USD[vendor]
    counts = topo.counts
    lines = [
        BomLine("Router/Firewall de borde", counts.get("edge", 0), price["edge"]),
        BomLine("Router/Firewall de distribución", counts.get("dist", 0), price["dist"]),
        BomLine("Switch núcleo L3", counts.get("core", 0), price["core"]),
        BomLine("Switch de acceso 48p", counts.get("access", 0), price["access"]),
    ]
    if counts.get("router"):
        lines.append(BomLine("Router adicional (topología cargada)", counts["router"], price["edge"]))
    if counts.get("server"):
        lines.append(BomLine("Switch granja de servidores", counts["server"], price["server"]))
    if cfg.has("Wi-Fi"):
        lines.append(BomLine("Access Point Wi-Fi 6", cfg.ap_per_floor * cfg.floors, price["ap"]))
    if cfg.has("CCTV"):
        lines.append(BomLine("Cámara IP PoE", cfg.cameras_per_floor * cfg.floors, price["cam"]))
    return [l for l in lines if l.qty]


def total_cost(lines: list[BomLine]) -> int:
    return sum(l.total for l in lines)


def bandwidth_demand_mbps(cfg: ProjectConfig) -> dict[str, float]:
    demand = {"Datos": cfg.hosts_total * KBPS_PER_USER_DATA / 1000 * 0.2}  # 20 % simultaneidad
    if cfg.has("VoIP"):
        demand["VoIP"] = cfg.hosts_total * VOIP_CONCURRENCY * VOIP_KBPS_PER_CALL / 1000
    if cfg.has("CCTV"):
        demand["CCTV remoto"] = cfg.cameras_per_floor * cfg.floors * CCTV_MBPS_PER_CAM_UPLINK * 0.25
    if cfg.has("Wi-Fi"):
        demand["Wi-Fi"] = demand["Datos"] * WIFI_FACTOR
    return {k: round(v, 1) for k, v in demand.items()}
