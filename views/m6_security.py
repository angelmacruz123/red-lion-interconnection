"""Módulo 6 — Ciberdefensa integrada y pruebas (% de confianza)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core import quality
from core.validators import ValidationError, is_destructive, redact_secrets, validate_command
from ui.components import Stat, callout, hero, section, stat_grid


def render() -> None:
    report: quality.QualityReport | None = st.session_state.get("last_test_report")
    checks = quality.security_checks()
    sec_ok = sum(c.ok for c in checks)

    if report:
        tone = "ok" if report.confidence >= 90 else "warn" if report.confidence >= 75 else "bad"
        status = f"Confianza {report.confidence} %"
    else:
        tone, status = "warn", "Pruebas sin ejecutar"
    hero("Módulo 6 · Ciberdefensa", "Seguridad y porcentaje de confianza",
         "Validación estricta de entradas, prevención de inyección y XSS, anti-fuga de credenciales "
         "(.env + .gitignore) y reporte automático de pruebas para docs/pruebas.md.", status, tone)

    tests_ok = sum(t.ok for t in report.tests) if report else 0
    tests_total = len(report.tests) if report else 0
    stat_grid([
        Stat("Confianza del sistema", f"{report.confidence} %" if report else "—",
             "60 % pruebas · 25 % seguridad · 15 % cobertura", report.confidence if report else 0, tone),
        Stat("Pruebas superadas", f"{tests_ok} / {tests_total}" if report else "—",
             f"{report.duration_s:.1f} s" if report else "ejecute la batería",
             100 * report.pass_rate if report else 0, "ok" if report and report.pass_rate == 1 else "warn"),
        Stat("Controles de seguridad", f"{sec_ok} / {len(checks)}", "repositorio y secretos",
             100 * sec_ok / len(checks), "ok" if sec_ok == len(checks) else "warn"),
        Stat("Categorías cubiertas", f"{round(report.coverage_score * len(quality.CATEGORIES))} / "
             f"{len(quality.CATEGORIES)}" if report else "—", "módulos con pruebas OK",
             100 * report.coverage_score if report else 0),
    ])

    c1, c2 = st.columns([1, 1])
    if c1.button("Ejecutar batería de pruebas y generar docs/pruebas.md", type="primary",
                 width="stretch"):
        with st.spinner("Ejecutando pytest (unitarias, seguridad e interfaz)…"):
            report = quality.build_report()
            path = quality.write_report(report)
        st.session_state["last_test_report"] = report
        st.toast(f"Reporte escrito en {path.relative_to(quality.ROOT)}", icon="📄")
        st.rerun()
    if report:
        c2.download_button("Descargar pruebas.md", quality.render_markdown(report).encode("utf-8"),
                           "pruebas.md", "text/markdown", width="stretch")

    t1, t2, t3 = st.tabs(["Controles de seguridad", "Resultados de pruebas", "Laboratorio de validación"])
    with t1:
        st.dataframe(pd.DataFrame([{"Estado": "✅" if c.ok else "❌", "Control": c.name, "Detalle": c.detail}
                                   for c in checks]), hide_index=True, width="stretch")
        callout("Regla de oro: las credenciales viven solo en .env (excluido por .gitignore) o en un "
                "gestor de secretos. Las configuraciones generadas usan marcadores <<...>>.", "ok")
    with t2:
        if not report:
            callout("Aún no hay resultados. Ejecute la batería para calcular el porcentaje de confianza.")
        else:
            cats = report.by_category()
            st.dataframe(pd.DataFrame([{"Categoría": k, "Módulo": v, "OK": cats.get(k, (0, 0))[0],
                                        "Total": cats.get(k, (0, 0))[1]}
                                       for k, v in quality.CATEGORIES.items()]),
                         hide_index=True, width="stretch")
            failed = [t for t in report.tests if not t.ok]
            if failed:
                st.error("\n".join(f"{t.category}::{t.name} — {t.message}" for t in failed))
    with t3:
        section("Probar un comando contra el filtro anti-inyección")
        cmd = st.text_input("Comando", "show running-config | include hostname ; reload")
        try:
            ok = validate_command(cmd)
            if is_destructive(ok):
                st.warning(f"Válido pero DESTRUCTIVO: requiere confirmación explícita → `{ok}`")
            else:
                st.success(f"Comando aceptado → `{ok}`")
        except ValidationError as exc:
            st.error(f"Bloqueado: {exc}")
        section("Enmascarado de secretos en salidas y logs")
        sample = st.text_area("Salida de un equipo", "username netadmin secret 9 $9$abc123XYZ\n"
                              "snmp-server community Publica123 RO\nset psksecret ENC hXk29sd==\n"
                              "/user add name=ops password=Sup3rS3creta", height=110)
        st.code(redact_secrets(sample), language="text")
