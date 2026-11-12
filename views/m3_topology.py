"""Módulo 3 — Topología y modelado estructural."""

from __future__ import annotations

import json
import shutil
import subprocess

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from core import topology_io as tio
from core.ipam import build_address_plan
from core.state import clear_topology_override, get_config, get_plan, set_topology_override
from core.topology import build_topology, to_dot, to_mermaid
from core.validators import ValidationError
from ui.components import Stat, callout, hero, section, stat_grid


def render() -> None:
    cfg = get_config()
    try:
        plan, topo = get_plan()
    except ValidationError as exc:
        callout(str(exc), "bad")
        return

    hero("Módulo 3 · Topología", "Carga y modelado de la topología",
         "La herramienta propone la arquitectura jerárquica desde el plan IP; usted puede editarla o importar la suya "
         "(dispositivos, roles, enlaces WAN e ISP). Lo cargado alimenta el diagrama y las configuraciones.",
         f"{'Topología cargada' if topo.custom else 'Topología propuesta'} · {len(topo.devices)} nodos · "
         f"{len(topo.edges)} enlaces", "warn" if topo.custom else "ok")
    if st.session_state.pop("topo_override_dropped", False):
        callout("El diseño cambió en el Módulo 1, así que la topología cargada se descartó. Vuelva a importarla.",
                "warn")

    counts = topo.counts
    stat_grid([
        Stat("Capa de borde", str(counts.get("edge", 0) + counts.get("isp", 0)), "ISP + router core"),
        Stat("Distribución", str(counts.get("dist", 0)), "OSPF área 0"),
        Stat("Núcleo", str(counts.get("core", 0)), f"{len([s for s in plan.segments if s.role != 'dmz'])} SVIs"),
        Stat("Acceso", str(counts.get("access", 0)), f"{cfg.floors} pisos · 48 puertos c/u"),
    ])

    dot = to_dot(topo, cfg.project_name)
    mmd = to_mermaid(topo)
    t0, t1, t2, t3 = st.tabs(["Cargar / editar topología", "Diagrama (Graphviz)",
                              "Diagrama interactivo (Mermaid)", "Inventario"])
    with t0:
        _loader(cfg, plan, topo)
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


def _loader(cfg, plan, topo) -> None:
    """Ingresar, editar, importar y exportar dispositivos y enlaces."""
    callout("Edite las tablas (puede agregar o quitar filas) o importe un archivo y pulse «Aplicar topología». "
            "Roles: " + ", ".join(tio.ROLES) + ". Tipos de enlace: " + ", ".join(tio.LINK_TYPES) +
            ". Un enlace «wan» entre routers recibe su /30 automáticamente.")
    with st.expander("Importar desde archivo (JSON o CSV)"):
        a, b, c = st.columns(3)
        fj = a.file_uploader("Topología completa (.json)", type=["json"], key="up_json")
        fd = b.file_uploader("Dispositivos (.csv)", type=["csv"], key="up_dev")
        fl = c.file_uploader("Enlaces (.csv)", type=["csv"], key="up_links")
        if st.button("Importar archivo(s)", disabled=not (fj or (fd and fl))):
            try:
                if fj:
                    devices, links = tio.from_json(fj.getvalue())
                else:
                    devices = tio.from_csv(fd.getvalue(), tio.DEVICE_COLUMNS)
                    links = tio.from_csv(fl.getvalue(), tio.LINK_COLUMNS)
                _apply(cfg, plan, devices, links)
            except ValidationError as exc:
                st.error(f"Importación rechazada:\n\n{exc}")

    devices, links = tio.topology_to_tables(topo)
    version = (st.session_state.get("topo_override") or {}).get("version", "base") + cfg.fingerprint()
    section(f"Dispositivos ({len(devices)})")
    dev_df = st.data_editor(
        pd.DataFrame(devices, columns=list(tio.DEVICE_COLUMNS)).astype({"piso": "string"}),
        num_rows="dynamic", hide_index=True, width="stretch", key=f"ed_dev_{version}",
        column_config={"rol": st.column_config.SelectboxColumn("rol", options=list(tio.ROLES), required=True),
                       "piso": st.column_config.TextColumn("piso", help="Solo switches de acceso: 1…" + str(cfg.floors)),
                       "ip_gestion": st.column_config.TextColumn("ip_gestion",
                                                                 help=f"Dentro de {plan.segment('mgmt').network}")})
    section(f"Enlaces ({len(links)})")
    link_df = st.data_editor(
        pd.DataFrame(links, columns=list(tio.LINK_COLUMNS)), num_rows="dynamic", hide_index=True,
        width="stretch", key=f"ed_links_{version}",
        column_config={"tipo": st.column_config.SelectboxColumn("tipo", options=list(tio.LINK_TYPES), required=True)})

    c1, c2, c3, c4 = st.columns(4)
    if c1.button("Aplicar topología", type="primary", width="stretch"):
        try:
            _apply(cfg, plan, dev_df.fillna("").to_dict("records"), link_df.fillna("").to_dict("records"))
        except ValidationError as exc:
            st.error(f"Topología rechazada por la validación:\n\n{exc}")
    if c2.button("Restablecer la propuesta", width="stretch", disabled=not topo.custom):
        clear_topology_override()
        st.rerun()
    c3.download_button("Exportar .json", tio.to_json(topo).encode("utf-8"),
                       f"topologia_{cfg.hostname_prefix}.json", "application/json", width="stretch")
    c4.download_button("Exportar .csv (dispositivos)", tio.devices_csv(topo).encode("utf-8"),
                       f"dispositivos_{cfg.hostname_prefix}.csv", "text/csv", width="stretch")
    if topo.extra_links:
        section("Enlaces WAN agregados (/30 asignados automáticamente)")
        st.dataframe(pd.DataFrame([{"Enlace": l.name, "Lado A": l.a_device, "IP A": str(l.a_ip),
                                    "Lado B": l.b_device, "IP B": str(l.b_ip), "Red /30": str(l.network)}
                                   for l in topo.extra_links]), hide_index=True, width="stretch")


def _apply(cfg, plan, devices: list[dict], links: list[dict]) -> None:
    """Valida contra la topología propuesta y, si todo es correcto, la guarda en el estado global."""
    base = build_topology(cfg, build_address_plan(cfg))
    tio.build_from_tables(cfg, plan, base, devices, links)  # lanza ValidationError con todos los errores
    clean = [{k: ("" if v is None else str(v).strip()) for k, v in r.items()} for r in devices]
    clean_links = [{k: ("" if v is None else str(v).strip()) for k, v in r.items()} for r in links]
    set_topology_override(clean, clean_links)
    st.toast("Topología cargada: diagrama y configuraciones actualizados", icon="✅")
    st.rerun()


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
