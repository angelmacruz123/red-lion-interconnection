"""UI · Cada módulo de Streamlit se ejecuta sin excepciones (streamlit.testing.AppTest)."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")
MODULES = ["01  Requerimientos", "02  Planificación IP", "03  Topología", "04  Configuraciones",
           "05  Conexión y despliegue", "06  Ciberdefensa y pruebas"]


def _open(module: str) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=90)
    at.run()
    at.sidebar.radio(key="nav").set_value(module).run()
    return at


def _button(at: AppTest, startswith: str):
    return next(b for b in at.button if b.label.startswith(startswith))


@pytest.mark.parametrize("module", MODULES)
def test_modulo_renderiza_sin_errores(module):
    at = _open(module)
    assert not at.exception, at.exception


def test_estado_global_sincroniza_modulos():
    at = AppTest.from_file(APP, default_timeout=90)
    at.run()
    at.selectbox[0].set_value("Sucursal pequeña (1 piso)").run()
    _button(at, "Aplicar plantilla").click().run()
    assert at.session_state["config"].floors == 1
    at.sidebar.radio(key="nav").set_value("02  Planificación IP").run()
    assert not at.exception
    assert "1 pisos" in " ".join(m.value for m in at.sidebar.markdown)


def test_despliegue_simulado_configura_el_equipo():
    at = _open("05  Conexión y despliegue")
    _button(at, "Desplegar en").click().run()
    assert not at.exception, at.exception
    assert any("configurado" in s.value for s in at.success)
    states = at.session_state["sim_states"]
    state = next(iter(states.values()))
    assert {"hostname", "ip"} <= state.applied
    assert state.hostname.endswith("R-CORE")


def test_terminal_simulada_ejecuta_lote():
    at = _open("05  Conexión y despliegue")
    _button(at, "Ejecutar lote").click().run()
    assert not at.exception
    history = at.session_state["console_history"]
    assert any("show ip interface brief" in c for _, c, _ in history)


def test_terminal_bloquea_inyeccion():
    at = _open("05  Conexión y despliegue")
    at.text_area(key="cmds_Cisco").set_value("show ver ; reload").run()
    _button(at, "Ejecutar lote").click().run()
    assert any("rechazado" in e.value for e in at.error)


def test_modo_consola_serial_renderiza():
    at = _open("05  Conexión y despliegue")
    at.session_state["console_mode"] = "Consola serial (COM)"
    at.run()
    assert not at.exception, at.exception
    assert any(s.label == "Velocidad" for s in at.selectbox)


def test_carga_de_topologia_desde_la_interfaz():
    at = _open("03  Topología")
    _button(at, "Aplicar topología").click().run()
    assert not at.exception, at.exception
    assert at.session_state["topo_override"]["devices"]
    assert any("Topología cargada" in m.value for m in at.markdown)
    at.sidebar.radio(key="nav").set_value("04  Configuraciones").run()
    assert not at.exception
