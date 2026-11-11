"""Módulo 5 — Conexión a equipos: despliegue guiado de configuración y terminal NetDevOps."""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime

import streamlit as st

from core.state import VENDORS, get_config, get_plan
from core.validators import ValidationError, parse_command_batch, redact_secrets
from generators import render_device
from generators.common import Ctx
from netdevops.deploy import CATEGORIES, DEFAULT_CATEGORIES, SECRET_ENV, build_deploy_plan, execute
from netdevops.simulator import LabSimulator, SimState
from netdevops.serial_client import BAUD_RATES, SerialConsoleSession, list_serial_ports
from netdevops.ssh_client import ConnectionParams, SSHSession, TransportError, env_bool
from netdevops.telnet_client import TelnetLabSession
from ui.components import Stat, callout, hero, section, stat_grid, terminal

from .m4_configs import get_extras

PRESETS = {
    "Cisco": "show version\nshow ip interface brief\nshow vlan brief\nshow ip route\nshow ip ospf neighbor",
    "Huawei": "display version\ndisplay ip interface brief\ndisplay vlan\ndisplay ip routing-table\ndisplay ospf peer brief",
    "Fortinet": "get system status\nget system interface\nget router info routing-table all\nget router info ospf neighbor",
    "MikroTik": "/system resource print\n/ip address print\n/ip route print\n/routing ospf neighbor print",
}
MAX_HISTORY = 300
MODES = ["Simulación", "Consola serial (COM)", "SSH", "Telnet (lab)"]
SERIAL = "Consola serial (COM)"


@dataclass
class Conn:
    mode: str
    vendor: str
    device: object
    host: str = ""
    port: int = 22
    user: str = ""
    password: str = ""
    enable_secret: str = ""
    baud: int = 9600

    @property
    def target(self) -> str:
        return self.host if self.mode != SERIAL else f"{self.host} @ {self.baud} baudios"


# --------------------------------------------------------------------------- #
# Estado de los equipos simulados (persisten mientras dure la sesión)
# --------------------------------------------------------------------------- #

def sim_state(vendor: str, device) -> SimState:
    cfg = get_config()
    store = st.session_state.setdefault("sim_states", {})
    key = (cfg.fingerprint(), vendor, device.id)
    if key not in store:
        store[key] = SimState.factory(vendor, device)
    return store[key]


@contextmanager
def open_transport(conn: Conn, ctx: Ctx):
    """Entrega un objeto con run() y send_lines() según el modo elegido."""
    if conn.mode == "Simulación":
        text = render_device(ctx, conn.vendor, conn.device.id).text
        yield LabSimulator(ctx.plan, ctx.topo, conn.device, conn.vendor, text, sim_state(conn.vendor, conn.device))
    elif conn.mode == SERIAL:
        with SerialConsoleSession(conn.host, conn.baud, conn.user, conn.password, conn.vendor,
                                  conn.enable_secret) as console:
            yield console
    elif conn.mode == "SSH":
        params = ConnectionParams(conn.host, conn.user, conn.password, int(conn.port), conn.vendor)
        with SSHSession(params) as session:
            session.ensure_privileged(conn.enable_secret)
            yield session
    else:
        with TelnetLabSession(conn.host, conn.user, conn.password, int(conn.port)) as tn:
            yield tn


def _prompt(conn: Conn, transport) -> str:
    if isinstance(transport, LabSimulator):
        return transport.prompt()
    return f"{conn.device.hostname}#"


# --------------------------------------------------------------------------- #
# Vista principal
# --------------------------------------------------------------------------- #

def render() -> None:
    cfg = get_config()
    try:
        plan, topo = get_plan()
    except ValidationError as exc:
        callout(str(exc), "bad")
        return
    ctx = Ctx(cfg, plan, topo, get_extras())

    hero("Módulo 5 · Conexión a equipos", "Despliegue guiado y terminal",
         "La app se conecta a la terminal de cada equipo y aplica, en orden, lo que ya diseñó: nombre, VLAN, "
         "direcciones IP y encendido de puertos. Respalda antes, se detiene ante cualquier error y verifica al final.",
         "SSH estricto" if not env_bool("ALLOW_UNKNOWN_HOSTS") else "SSH modo laboratorio",
         "ok" if not env_bool("ALLOW_UNKNOWN_HOSTS") else "warn")

    conn = _connection_panel(topo, cfg)
    tab_deploy, tab_term = st.tabs(["Despliegue guiado", "Terminal de comandos"])
    with tab_deploy:
        _deploy_tab(conn, ctx)
    with tab_term:
        _terminal_tab(conn, ctx)


def _connection_panel(topo, cfg) -> Conn:
    section("1 · Conexión")
    devices = [d for d in topo.devices if d.role in ("edge", "dist", "core", "access", "server")]
    roles = {"edge": "Borde", "dist": "Distribución", "core": "Núcleo", "access": "Acceso", "server": "Servidores"}
    a, b, c = st.columns([1.9, 0.9, 1.5])
    mode = a.segmented_control("Modo", MODES, default="Simulación", key="console_mode") or "Simulación"
    vendor = b.selectbox("Fabricante", VENDORS, index=VENDORS.index(cfg.vendor), key="console_vendor")
    idx = c.selectbox("Equipo del diseño", range(len(devices)), key="console_device",
                      format_func=lambda i: f"{roles[devices[i].role]} · {devices[i].hostname} · {devices[i].mgmt_ip}")
    dev = devices[idx]
    conn = Conn(mode, vendor, dev)
    if mode == "Simulación":
        st.caption("Simulación: cada equipo arranca de fábrica (sin nombre, VLAN ni IP) y cambia a medida "
                   "que le despliegas configuración. Ideal para demostrar el flujo sin hardware.")
        return conn

    if mode == SERIAL:
        ports = list_serial_ports()
        a, b, c, d, e = st.columns([1.4, 0.8, 1, 1, 1])
        options = [p for p, _ in ports] + ["Otro…"]
        pick = a.selectbox("Puerto COM", options, key="serial_pick",
                           format_func=lambda x: next((f"{p} · {d}" for p, d in ports if p == x), x))
        conn.host = (a.text_input("Puerto manual", "COM1", key="serial_manual") if pick == "Otro…" else pick)
        conn.baud = int(b.selectbox("Velocidad", BAUD_RATES, index=0, key="serial_baud"))
        conn.user = c.text_input("Usuario (si pide)", os.getenv("NET_USERNAME", ""), key="serial_user")
        pwd = d.text_input("Contraseña (si pide)", type="password", placeholder="vacío = .env", key="serial_pwd")
        ena = e.text_input("Enable (si pide)", type="password", placeholder="vacío = .env", key="serial_ena")
        conn.password = pwd or os.getenv("NET_PASSWORD", "")
        conn.enable_secret = ena or os.getenv("ENABLE_SECRET", "")
        if not ports:
            callout("No se detectan puertos COM. Conecte el cable de consola (USB o adaptador USB-serial) y "
                    "revise el número en Administrador de dispositivos → Puertos (COM y LPT). "
                    "Cierre PuTTY si lo tiene abierto: el puerto solo admite un programa a la vez.", "warn")
        else:
            st.caption("Configuración 8N1 sin control de flujo (igual que PuTTY → Serial). Un equipo de fábrica "
                       "no pide usuario: deje los campos vacíos. La app responde sola al diálogo inicial de Cisco.")
        return conn

    a, b, c, d, e = st.columns([1.4, 0.7, 1, 1, 1])
    conn.host = a.text_input("Host / IP de gestión", dev.mgmt_ip, key=f"host_{dev.id}",
                             help="Por defecto, la IP de gestión que el plan asignó a este equipo.")
    conn.port = int(b.number_input("Puerto", 1, 65535, 22 if mode == "SSH" else 23, key=f"port_{mode}"))
    conn.user = c.text_input("Usuario", os.getenv("NET_USERNAME", "netadmin"))
    pwd = d.text_input("Contraseña", type="password", placeholder="vacío = .env")
    ena = e.text_input("Enable (Cisco)", type="password", placeholder="vacío = .env")
    conn.password = pwd or os.getenv("NET_PASSWORD", "")
    conn.enable_secret = ena or os.getenv("ENABLE_SECRET", "")
    if mode == "Telnet (lab)":
        callout("Telnet viaja sin cifrar: solo IP privadas y con ENABLE_TELNET_LAB=true en el .env.", "warn")
    else:
        st.caption("Si el equipo es nuevo, primero agregue su clave: ssh-keyscan -H <IP> >> ~/.ssh/known_hosts "
                   "(o, solo en laboratorio, ALLOW_UNKNOWN_HOSTS=true).")
    return conn


# --------------------------------------------------------------------------- #
# Pestaña: despliegue guiado
# --------------------------------------------------------------------------- #

def _deploy_tab(conn: Conn, ctx: Ctx) -> None:
    dev = conn.device
    section("2 · Qué configurar")
    cols = st.columns(4)
    chosen = []
    for i, (key, label) in enumerate(CATEGORIES.items()):
        if cols[i % 4].checkbox(label, value=key in DEFAULT_CATEGORIES, key=f"cat_{key}"):
            chosen.append(key)
    with st.expander("Opciones avanzadas"):
        a, b, c, d = st.columns(4)
        do_backup = a.toggle("Respaldar antes", True)
        do_verify = b.toggle("Verificar al final", True)
        do_save = c.toggle("Guardar en el equipo", True,
                           help="write memory / save. Si se desactiva, un reinicio deshace los cambios.")
        stop = d.toggle("Detener en el primer error", True)
        missing = [env for env in SECRET_ENV.values() if not os.getenv(env)]
        st.caption("Secretos disponibles en .env: "
                   + (", ".join(e for e in SECRET_ENV.values() if os.getenv(e)) or "ninguno")
                   + ". Los bloques que necesitan uno ausente se omiten automáticamente."
                   + (f" Faltan: {', '.join(missing)}." if missing else ""))

    if not chosen:
        callout("Seleccione al menos una categoría.", "warn")
        return
    try:
        plan = build_deploy_plan(ctx, conn.vendor, dev.id, chosen, save=do_save)
    except ValidationError as exc:
        callout(str(exc), "bad")
        return

    section("3 · Vista previa (exactamente lo que se enviará)")
    counts = plan.count_by_category()
    stat_grid([
        Stat("Equipo destino", dev.hostname, f"{conn.vendor} · {conn.mode}"),
        Stat("Líneas a enviar", str(len(plan.body_lines)), f"{len(plan.blocks)} bloques"),
        Stat("Categorías", str(len(plan.categories)), ", ".join(CATEGORIES[c].split(" (")[0] for c in counts)[:60]),
        Stat("Bloques omitidos", str(len(plan.skipped)), "por marcadores sin valor" if plan.skipped else "ninguno",
             tone="warn" if plan.skipped else "ok"),
    ])
    for note in plan.notes:
        st.info(note)
    if plan.skipped:
        with st.expander(f"Ver {len(plan.skipped)} bloques omitidos"):
            st.code("\n".join(plan.skipped), language="text")
    st.code(plan.preview(), language="cisco" if conn.vendor == "Cisco" else "bash", line_numbers=True, height=340)
    st.download_button("Descargar este lote (.txt)", plan.preview().encode(), f"despliegue_{dev.hostname}.txt",
                       width="content")

    section("4 · Confirmar y desplegar")
    if conn.mode == "Simulación":
        confirmed = True
        st.caption("En simulación no hace falta confirmación.")
    else:
        callout(f"Esto modificará la configuración en vivo de {conn.target}. Asegúrese de tener acceso por consola "
                "por si algo falla.", "warn")
        typed = st.text_input(f"Escriba el nombre del equipo ({dev.hostname}) para confirmar", key=f"confirm_{dev.id}")
        confirmed = typed.strip() == dev.hostname

    c1, c2 = st.columns([2, 1])
    go = c1.button(f"Desplegar en {dev.hostname}", type="primary", width="stretch", disabled=not confirmed)
    if conn.mode == "Simulación" and c2.button("Restablecer equipo simulado", width="stretch"):
        st.session_state.get("sim_states", {}).pop((get_config().fingerprint(), conn.vendor, dev.id), None)
        st.rerun()

    screen = st.empty()
    log_key = f"deploy_log_{conn.vendor}_{dev.id}"
    if go:
        entries: list = [("#meta", "", f"── {datetime.now():%H:%M:%S} · {conn.mode} · {dev.hostname} · "
                                       f"{', '.join(plan.categories)} ──")]
        ok_blocks, failed = 0, False
        progress = st.progress(0.0, text="Conectando…")
        total = len(plan.blocks)
        try:
            with open_transport(conn, ctx) as tr:
                if isinstance(tr, SSHSession):
                    entries += [("#meta", "", w) for w in tr.warnings]
                for step in execute(plan, tr, backup=do_backup, verify=do_verify, stop_on_error=stop):
                    label = {"backup": "respaldo", "config": "config", "save": "guardar",
                             "verify": "verificación", "info": "estado"}[step.phase]
                    if step.phase == "config" and step.sent not in ("\n".join(plan.pre),):
                        ok_blocks += step.ok
                        progress.progress(min(1.0, ok_blocks / max(total, 1)),
                                          text=f"Bloque {ok_blocks}/{total}")
                    if not step.ok:
                        failed = True
                    entries.append((f"[{label}] {_prompt(conn, tr)}", step.sent.splitlines()[0] if step.sent else "",
                                    step.output if step.phase != "config" or not step.ok else
                                    step.output[-1200:]))
                    terminal(f"{dev.hostname} — despliegue", entries[-MAX_HISTORY:], screen)
        except (TransportError, ValidationError, OSError) as exc:
            failed = True
            entries.append(("#meta", "", f"% Error de conexión: {exc}"))
        progress.empty()
        st.session_state[log_key] = entries
        if failed:
            st.error(f"Despliegue incompleto en {dev.hostname}: {ok_blocks}/{total} bloques aplicados. "
                     "Revise el error en la terminal; el respaldo quedó en configs_out/backups/.")
        else:
            st.success(f"{dev.hostname} configurado: {ok_blocks}/{total} bloques aplicados y verificados.")
            st.session_state.setdefault("deployed", {})[(conn.vendor, dev.id)] = plan.categories

    entries = st.session_state.get(log_key)
    terminal(f"{dev.hostname} — despliegue", entries or [("#meta", "", "Listo para desplegar.")], screen)
    if entries:
        log = "\n".join(f"{p} {c}\n{o}" for p, c, o in entries)
        st.download_button("Descargar log del despliegue", log.encode(), f"log_{dev.hostname}.txt", width="content")

    deployed = st.session_state.get("deployed", {})
    if deployed:
        section("Equipos configurados en esta sesión")
        st.dataframe([{"Fabricante": v, "Equipo": ctx.topo.get(d).hostname, "Categorías": ", ".join(c)}
                      for (v, d), c in deployed.items()], hide_index=True, width="stretch")


# --------------------------------------------------------------------------- #
# Pestaña: terminal libre (comandos de consulta)
# --------------------------------------------------------------------------- #

def _terminal_tab(conn: Conn, ctx: Ctx) -> None:
    dev = conn.device
    a, b = st.columns([3, 1])
    cmds_text = a.text_area("Un comando por línea (# o ! = comentario)", PRESETS[conn.vendor],
                            height=150, key=f"cmds_{conn.vendor}")
    allow_destructive = b.toggle("Permitir destructivos (reload, erase…)", value=False)
    run = b.button("Ejecutar lote", type="primary", width="stretch")
    if b.button("Limpiar", width="stretch"):
        st.session_state["console_history"] = []
    history: list = st.session_state.setdefault("console_history", [])
    log = "\n".join(f"{p} {c}\n{o}" for p, c, o in history)
    b.download_button("Log .txt", log.encode(), f"consola_{datetime.now():%Y%m%d_%H%M}.txt",
                      width="stretch", disabled=not log)
    screen = st.empty()
    title = f"{dev.hostname} — {conn.mode.lower()} — {conn.vendor}"

    if run:
        try:
            commands = parse_command_batch(cmds_text, allow_destructive=allow_destructive)
        except ValidationError as exc:
            st.error(f"Lote rechazado por la validación de seguridad: {exc}")
            commands = []
        if commands:
            history.append(("#meta", "", f"── {datetime.now():%H:%M:%S} · {conn.mode} · {dev.hostname} ──"))
            try:
                with open_transport(conn, ctx) as tr:
                    history.extend(("#meta", "", w) for w in getattr(tr, "warnings", []))
                    for c in commands:
                        r = tr.run(c)
                        history.append((_prompt(conn, tr), r.command,
                                        redact_secrets(r.output, [conn.password, conn.enable_secret])))
                        terminal(title, history[-MAX_HISTORY:], screen)
            except (TransportError, ValidationError, OSError) as exc:
                history.append(("#meta", "", f"% Error de conexión: {exc}"))
        del history[:-MAX_HISTORY]

    view = history or [("#meta", "", "Listo. En simulación, escriba 'help' para ver los comandos disponibles.")]
    terminal(title, view[-MAX_HISTORY:], screen)
