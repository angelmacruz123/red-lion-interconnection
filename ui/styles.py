"""
ui/styles.py — Sistema de diseño RED-LION: negro carbón con acentos rojo carmesí.

Tokens de color y tipografía centralizados. Se inyecta una sola vez por
ejecución desde app.py.
"""

TOKENS = {
    "bg": "#0a0708",
    "panel": "#120c0d",
    "panel_2": "#181011",
    "border": "#2a1719",
    "border_hi": "#3d2024",
    "text": "#f4eeee",
    "muted": "#b8a6a8",
    "faint": "#806b6e",
    "accent": "#ef233c",
    "accent_soft": "rgba(239,35,60,.12)",
    "ok": "#34d399",
    "warn": "#fbbf24",
    "bad": "#f87171",
}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --bg:#0a0708; --panel:#120c0d; --panel2:#181011; --border:#2a1719; --border-hi:#3d2024;
  --text:#f4eeee; --muted:#b8a6a8; --faint:#806b6e; --accent:#ef233c;
  --accent-soft:rgba(239,35,60,.12); --ok:#34d399; --warn:#fbbf24; --bad:#ff6b6b;
  --radius:10px; --mono:'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
}

html, body, [class*="css"], .stMarkdown, .stText, button, input, textarea, select {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
  -webkit-font-smoothing: antialiased;
}
.stApp { background:
  radial-gradient(1200px 520px at 85% -12%, rgba(239,35,60,.16), transparent 60%),
  radial-gradient(900px 420px at -10% 110%, rgba(127,13,22,.22), transparent 60%),
  var(--bg); }

/* Ocultar cromo de Streamlit */
#MainMenu, footer, [data-testid="stDecoration"] { display:none !important; }
header[data-testid="stHeader"] { background: transparent; }

.block-container { padding-top: 1.6rem; padding-bottom: 4rem; max-width: 1280px; }

/* Sidebar */
section[data-testid="stSidebar"] { background: #0d0809; border-right: 1px solid var(--border); }
section[data-testid="stSidebar"] .stRadio > div { gap: 2px; }
section[data-testid="stSidebar"] .stRadio label {
  padding: 7px 10px; border-radius: 8px; width: 100%; transition: background .15s;
  color: var(--muted) !important; font-size: 13.5px;
}
section[data-testid="stSidebar"] .stRadio label:hover { background: #1d1112; color: var(--text) !important; }
section[data-testid="stSidebar"] .stRadio label:has(input:checked) {
  background: var(--accent-soft); color: var(--text) !important; box-shadow: inset 2px 0 0 var(--accent);
}
section[data-testid="stSidebar"] .stRadio label > div:first-child { display:none; }

/* Tipografía */
h1, h2, h3 { letter-spacing: -0.02em; color: var(--text); }
h1 { font-weight: 650; }
p, li { color: #e6dcdd; }
code { font-family: var(--mono) !important; }

/* Inputs */
.stTextInput input, .stNumberInput input, .stTextArea textarea, div[data-baseweb="select"] > div {
  background: var(--panel) !important; border: 1px solid var(--border) !important; border-radius: 8px !important;
}
.stTextInput input:focus, .stTextArea textarea:focus { border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px var(--accent-soft) !important; }
.stTextArea textarea { font-family: var(--mono) !important; font-size: 13px !important; }

/* Botones */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
  border-radius: 8px; border: 1px solid var(--border-hi); background: #1a0f11; color: var(--text);
  font-weight: 500; font-size: 13.5px; padding: .45rem 1rem; transition: all .15s;
}
.stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover {
  border-color: var(--accent); color: #fff; background: #2a1316;
}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
  background: linear-gradient(180deg, #ff4d5e, #c1121f); border-color: #ff4d5e; color: #fff;
  box-shadow: 0 1px 0 rgba(255,255,255,.15) inset, 0 4px 14px rgba(239,35,60,.25);
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid var(--border); }
.stTabs [data-baseweb="tab"] { height: 38px; padding: 0 14px; color: var(--muted); font-size: 13.5px; }
.stTabs [aria-selected="true"] { color: var(--text) !important; }
.stTabs [data-baseweb="tab-highlight"] { background: var(--accent); }

/* Expanders / dataframes / métricas nativas */
details, [data-testid="stExpander"] { border: 1px solid var(--border) !important; border-radius: var(--radius) !important;
  background: var(--panel) !important; }
[data-testid="stDataFrame"] { border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; }
[data-testid="stMetric"] { background: var(--panel); border: 1px solid var(--border); border-radius: var(--radius); padding: 14px 16px; }
pre, .stCode { border-radius: var(--radius) !important; }
[data-testid="stCodeBlock"] pre { background: #0e0809 !important; border: 1px solid var(--border); }

/* ---------- Componentes propios ---------- */
.ewa-hero { display:flex; justify-content:space-between; align-items:flex-end; gap:16px; flex-wrap:wrap;
  padding: 4px 0 18px; border-bottom: 1px solid var(--border); margin-bottom: 22px; }
.ewa-eyebrow { font: 500 11.5px/1 var(--mono); color: var(--accent); letter-spacing:.08em; text-transform:uppercase; }
.ewa-title { font-size: 28px; font-weight: 650; letter-spacing: -0.025em; color: var(--text); margin: 8px 0 6px; }
.ewa-sub { color: var(--muted); font-size: 14.5px; max-width: 760px; margin:0; }
.ewa-pill { display:inline-flex; align-items:center; gap:6px; padding: 4px 10px; border-radius: 999px;
  border: 1px solid var(--border-hi); background: var(--panel); font: 500 12px/1.4 var(--mono); color: var(--muted); }
.ewa-dot { width:7px; height:7px; border-radius:50%; background: var(--ok); box-shadow: 0 0 8px var(--ok); }
.ewa-dot.warn { background: var(--warn); box-shadow: 0 0 8px var(--warn); }
.ewa-dot.bad { background: var(--bad); box-shadow: 0 0 8px var(--bad); }

.ewa-grid { display:grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 12px; margin: 6px 0 18px; }
.ewa-card { background: linear-gradient(180deg, #140c0e, #0f090a); border: 1px solid var(--border);
  border-radius: 12px; padding: 14px 16px; min-width:0; }
.ewa-card .k { font-size: 12px; color: var(--faint); text-transform: uppercase; letter-spacing:.06em; }
.ewa-card .v { font-size: 24px; font-weight: 600; color: var(--text); margin-top: 6px; letter-spacing:-.02em;
  font-variant-numeric: tabular-nums; white-space: nowrap; overflow:hidden; text-overflow: ellipsis; }
.ewa-card .s { font-size: 12.5px; color: var(--muted); margin-top: 2px; }
.ewa-bar { height: 5px; background: #2a1719; border-radius: 99px; overflow: hidden; margin-top: 10px; }
.ewa-bar > span { display:block; height:100%; background: var(--accent); border-radius: 99px; }
.ewa-bar > span.ok { background: var(--ok); } .ewa-bar > span.warn { background: var(--warn); } .ewa-bar > span.bad { background: var(--bad); }

.ewa-section { font-size: 13px; font-weight: 600; color: var(--muted); text-transform: uppercase;
  letter-spacing: .07em; margin: 22px 0 10px; }
.ewa-callout { border:1px solid var(--border); border-left: 3px solid var(--accent); background: var(--panel);
  border-radius: 8px; padding: 10px 14px; color: #e6dcdd; font-size: 13.5px; margin: 8px 0 14px; }
.ewa-callout.warn { border-left-color: var(--warn); } .ewa-callout.bad { border-left-color: var(--bad); }
.ewa-callout.ok { border-left-color: var(--ok); }

.ewa-brand { display:flex; align-items:center; gap:10px; padding: 4px 4px 14px; }
.ewa-logo { width: 28px; height: 28px; border-radius: 7px; display:grid; place-items:center;
  background: linear-gradient(135deg, #ff4d5e, #7f0d16); color:#fff; font: 700 13px/1 var(--mono);
  box-shadow: 0 4px 18px rgba(239,35,60,.45); }
.ewa-brand b { font-size: 14px; color: var(--text); } .ewa-brand small { display:block; color: var(--faint); font-size: 11.5px; }

/* Terminal estilo macOS */
.ewa-term { border: 1px solid #3a1d21; border-radius: 12px; overflow: hidden; background: #0d0809;
  box-shadow: 0 20px 50px rgba(0,0,0,.45); }
.ewa-term-bar { display:flex; align-items:center; gap:8px; padding: 10px 14px; background: #1a0e10; border-bottom: 1px solid #2e171a; }
.ewa-term-bar i { width:12px; height:12px; border-radius:50%; display:inline-block; }
.ewa-term-bar i:nth-child(1){background:#ff5f57} .ewa-term-bar i:nth-child(2){background:#febc2e} .ewa-term-bar i:nth-child(3){background:#28c840}
.ewa-term-bar span { margin-left: 10px; font: 500 12px var(--mono); color: var(--faint); }
.ewa-term-body { padding: 14px 16px; max-height: 520px; overflow: auto; font: 12.5px/1.55 var(--mono); color: #e6dcdd; white-space: pre; }
.ewa-term-body .p { color: #ff6b78; } .ewa-term-body .c { color: #fff; font-weight: 500; }
.ewa-term-body .e { color: var(--bad); } .ewa-term-body .m { color: var(--faint); }

/* Responsivo */
@media (max-width: 1000px) { .ewa-grid { grid-template-columns: repeat(2, minmax(0,1fr)); } }
@media (max-width: 560px) {
  .ewa-grid { grid-template-columns: 1fr; }
  .ewa-title { font-size: 22px; }
  .block-container { padding-left: 1rem; padding-right: 1rem; }
}
</style>
"""
