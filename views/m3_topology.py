"""Módulo 3 — Topología y modelado estructural."""

from __future__ import annotations

import json
import shutil
import subprocess

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from core.state import get_config, get_plan
from core.topology import to_dot, to_mermaid
from core.validators import ValidationError
from ui.components import Stat, callout, hero, section, stat_grid


def render() -> None:
    cfg = get_config()
    try:
        plan, topo = get_plan()
    except ValidationError as exc:
        callout(str(exc), "bad")
        return

    hero("Módulo 3 · Topología", "Arquitectura jerárquica",
         "Cloud ISP → Router Core → Router de Distribución → Switch Core → Acceso por piso → Servidores/DMZ. "
         "Cada nodo y enlace se dibuja desde el plan IP calculado; no hay datos inventados.",
         f"{len(topo.devices)} nodos · {len(topo.edges)} enlaces", "ok")

    counts = topo.counts
    stat_grid([
        Stat("Capa de borde", str(counts.get("edge", 0) + counts.get("isp", 0)), "ISP + router core"),
        Stat("Distribución", str(counts.get("dist", 0)), "OSPF área 0"),
        Stat("Núcleo", str(counts.get("core", 0)), f"{len([s for s in plan.segments if s.role != 'dmz'])} SVIs"),
        Stat("Acceso", str(counts.get("access", 0)), f"{cfg.floors} pisos · 48 puertos c/u"),
    ])

    dot = to_dot(topo, cfg.project_name)
    mmd = to_mermaid(topo)
    t1, t2, t3 = st.tabs(["Diagrama (Graphviz)", "Diagrama interactivo (Mermaid)", "Inventario"])
    with t1:
        st.graphviz_chart(dot, width="stretch")
    with t2:
        callout("Ctrl/⌘ + rueda del ratón para hacer zoom; desplácese con las barras o el trackpad.")
        _mermaid(mmd, height=720)
    with t3:
        rows = [{"Equipo": d.hostname, "Rol": d.role, "Capa": d.layer, "Piso": d.floor or "—",
                 "IP de gestión": d.mgmt_ip or "—", "Detalle": " · ".join(d.details)} for d in topo.devices]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        section("Enlaces")
        st.dataframe(pd.DataFrame([{"Origen": e.a, "Destino": e.b, "Tipo": e.kind, "Etiqueta": e.label}
                                   for e in topo.edges]), hide_index=True, width="stretch")

    section("Exportar")
    c1, c2, c3 = st.columns(3)
    c1.download_button("Graphviz (.dot)", dot, f"topologia_{cfg.hostname_prefix}.dot", width="stretch")
    c2.download_button("Mermaid (.mmd)", mmd, f"topologia_{cfg.hostname_prefix}.mmd", width="stretch")
    svg = _render_svg(dot)
    c3.download_button("Imagen (.svg)", svg or b"", f"topologia_{cfg.hostname_prefix}.svg", "image/svg+xml",
                       width="stretch", disabled=svg is None,
                       help=None if svg else "Instale Graphviz (binario 'dot') para exportar SVG.")


@st.cache_data(show_spinner=False)
def _render_svg(dot: str) -> bytes | None:
    if not shutil.which("dot"):
        return None
    try:
        res = subprocess.run(["dot", "-Tsvg"], input=dot.encode(), capture_output=True, timeout=20, check=True)
        return res.stdout
    except (subprocess.SubprocessError, OSError):
        return None


def _mermaid(code: str, height: int = 700) -> None:
    # El código se pasa como JSON (no interpolado como HTML) para evitar inyección.
    components.html(f"""
<div id="wrap" style="height:{height - 20}px;overflow:auto;background:#0d0809;border:1px solid #2a1719;border-radius:12px;">
  <div id="m" style="min-width:900px;padding:16px"></div>
</div>
<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
  mermaid.initialize({{ startOnLoad:false, theme:"dark", securityLevel:"strict",
    flowchart:{{ curve:"basis", htmlLabels:true, nodeSpacing:28, rankSpacing:60 }},
    themeVariables:{{ fontFamily:"Inter, sans-serif", fontSize:"12px", lineColor:"#4a2a2e" }} }});
  const code = {json.dumps(code)};
  const {{ svg }} = await mermaid.render("topo", code);
  const el = document.getElementById("m"); el.innerHTML = svg;
  let scale = 1; const s = el.querySelector("svg"); s.style.transformOrigin = "0 0";
  document.getElementById("wrap").addEventListener("wheel", e => {{
    if (!e.ctrlKey && !e.metaKey) return; e.preventDefault();
    scale = Math.min(3, Math.max(.3, scale - e.deltaY * .001)); s.style.transform = `scale(${{scale}})`; }},
    {{ passive:false }});
</script>""", height=height, scrolling=False)
