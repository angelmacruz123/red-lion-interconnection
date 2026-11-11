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
from .common import Ctx, Extras, GeneratedConfig, header

ENGINES = {"Cisco": cisco, "Huawei": huawei, "Fortinet": fortinet, "MikroTik": mikrotik}
CONFIGURABLE_ROLES = ("edge", "dist", "core", "access", "server")


def render_device(ctx: Ctx, vendor: str, device_id: str) -> GeneratedConfig:
    engine = ENGINES[vendor]
    dev = ctx.topo.get(device_id)
    body = engine.RENDER[dev.role](ctx, dev)
    platform = engine.PLATFORMS[dev.role]
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
