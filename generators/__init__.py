"""
generators — Módulo 4: motor de plantillas CLI multi-marca.

Uso:
    from generators import render_all, bundle_zip
    configs = render_all(cfg, plan, topo, "Cisco")
"""

from __future__ import annotations

import io
import zipfile

from core.ipam import AddressPlan
from core.state import ProjectConfig
from core.topology import Topology

from . import cisco, fortinet, huawei, mikrotik
from .common import Ctx, Extras, GeneratedConfig, extra_wan_lines, header

ENGINES = {"Cisco": cisco, "Huawei": huawei, "Fortinet": fortinet, "MikroTik": mikrotik}
CONFIGURABLE_ROLES = ("edge", "dist", "core", "access", "server", "router")

# Bloque final de cada fabricante (los enlaces WAN cargados se insertan antes)
_TRAILER = {"Cisco": ["end", "write memory"], "Huawei": ["return", "save"], "Fortinet": [], "MikroTik": []}


def _router(engine, vendor: str, ctx: Ctx, dev) -> str:
    """Router adicional cargado por el usuario: hardening + sus enlaces WAN."""
    hardening = {"Cisco": lambda: engine._hardening(ctx, dev.hostname) + ["ipv6 unicast-routing", "!"],
                 "Huawei": lambda: engine._hardening(ctx, dev.hostname),
                 "Fortinet": lambda: engine._global(ctx, dev.hostname),
                 "MikroTik": lambda: engine._hardening(ctx, dev.hostname)}[vendor]()
    return "\n".join(hardening + extra_wan_lines(vendor, ctx, dev) + _TRAILER[vendor])


def render_device(ctx: Ctx, vendor: str, device_id: str) -> GeneratedConfig:
    engine = ENGINES[vendor]
    dev = ctx.topo.get(device_id)
    if dev.role == "router":
        body = _router(engine, vendor, ctx, dev)
        platform = engine.PLATFORMS["edge"]
    else:
        body = engine.RENDER[dev.role](ctx, dev)
        platform = engine.PLATFORMS[dev.role]
        extra = extra_wan_lines(vendor, ctx, dev)
        if extra:
            lines, trailer = body.split("\n"), _TRAILER[vendor]
            if trailer and lines[-len(trailer):] == trailer:
                lines = lines[:-len(trailer)] + extra + trailer
            else:
                lines += extra
            body = "\n".join(lines)
    text = header(ctx, dev.hostname, vendor, platform, engine.COMMENT) + "\n" + body + "\n"
    return GeneratedConfig(dev.id, dev.hostname, vendor, dev.role, platform, text)


def render_all(cfg: ProjectConfig, plan: AddressPlan, topo: Topology, vendor: str,
               extras: Extras | None = None) -> list[GeneratedConfig]:
    if vendor not in ENGINES:
        raise ValueError(f"Fabricante no soportado: {vendor}")
    ctx = Ctx(cfg, plan, topo, extras or Extras())
    return [render_device(ctx, vendor, d.id) for d in topo.devices if d.role in CONFIGURABLE_ROLES]


def bundle_zip(configs: list[GeneratedConfig]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for c in configs:
            zf.writestr(c.filename, c.text)
    return buf.getvalue()


__all__ = ["ENGINES", "Extras", "GeneratedConfig", "render_all", "render_device", "bundle_zip"]
