"""
ui/components.py — Componentes visuales reutilizables.

Regla de seguridad: todo texto dinámico que se inserta en HTML pasa por
`esc()` (html.escape). Ninguna salida de equipo se pinta sin escapar.
"""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from core.validators import escape_output as esc

from .styles import CSS


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def hero(eyebrow: str, title: str, subtitle: str, status: str = "", tone: str = "ok") -> None:
    pill = (f'<span class="ewa-pill"><span class="ewa-dot {esc(tone)}"></span>{esc(status)}</span>'
            if status else "")
    st.markdown(
        f'<div class="ewa-hero"><div><div class="ewa-eyebrow">{esc(eyebrow)}</div>'
        f'<div class="ewa-title">{esc(title)}</div><p class="ewa-sub">{esc(subtitle)}</p></div>{pill}</div>',
        unsafe_allow_html=True,
    )


@dataclass
class Stat:
    label: str
    value: str
    sub: str = ""
    bar: float | None = None   # 0..100
    tone: str = ""             # "", ok, warn, bad


def stat_grid(stats: list[Stat]) -> None:
    cards = []
    for s in stats:
        bar = ""
        if s.bar is not None:
            pct = max(0.0, min(100.0, s.bar))
            bar = f'<div class="ewa-bar"><span class="{esc(s.tone)}" style="width:{pct:.1f}%"></span></div>'
        cards.append(f'<div class="ewa-card"><div class="k">{esc(s.label)}</div>'
                     f'<div class="v">{esc(s.value)}</div><div class="s">{esc(s.sub)}</div>{bar}</div>')
    st.markdown(f'<div class="ewa-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def section(title: str) -> None:
    st.markdown(f'<div class="ewa-section">{esc(title)}</div>', unsafe_allow_html=True)


def callout(text: str, tone: str = "") -> None:
    st.markdown(f'<div class="ewa-callout {esc(tone)}">{esc(text)}</div>', unsafe_allow_html=True)


def terminal(title: str, entries: list[tuple[str, str, str]], placeholder=None) -> None:
    """entries = [(prompt, comando, salida_o_error)]; salida que empieza por '% Error' se pinta en rojo."""
    body = []
    for prompt, cmd, out in entries:
        if prompt == "#meta":
            body.append(f'<span class="m">{esc(out)}</span>')
            continue
        body.append(f'<span class="p">{esc(prompt)}</span> <span class="c">{esc(cmd)}</span>')
        cls = "e" if out.lstrip().startswith(("% Error", "% Comando")) else ""
        safe = _nl(esc(out))
        body.append(f'<span class="{cls}">{safe}</span>' if cls else safe)
    html = (f'<div class="ewa-term"><div class="ewa-term-bar"><i></i><i></i><i></i>'
            f'<span>{esc(title)}</span></div><div class="ewa-term-body">{"<br/>".join(body) or "&nbsp;"}'
            f'</div></div>')
    (placeholder or st).markdown(html, unsafe_allow_html=True)


def _nl(text: str) -> str:
    """Saltos de línea → <br/> para que el parser Markdown no rompa el bloque HTML."""
    return text.replace("\r", "").replace("\n", "<br/>").replace("$", "&#36;")


def brand() -> None:
    st.markdown('<div class="ewa-brand"><div class="ewa-logo">RL</div>'
                '<div><b>RED-LION</b><small>INTERCONNECTION · NetDevOps</small></div></div>',
                unsafe_allow_html=True)
