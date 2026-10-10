# ruff: noqa: E501
from __future__ import annotations

from pathlib import Path

import humanize
import pandas as pd
import streamlit as st

RETRO_CSS = """
<style>
:root { --navy:#050a24; --panel:#07143a; --blue:#123a73; --cyan:#5de4ff; --amber:#ffd166; --green:#69f0ae; --paper:#d9f6ff; --muted:#89a9ba; --shadow:#01030e; --mono:"Cascadia Mono","SFMono-Regular",Consolas,monospace; }
html,body,[class*="css"],[data-testid="stAppViewContainer"] { font-family:var(--mono); }
[data-testid="stAppViewContainer"] { background:radial-gradient(circle at 72% -20%,rgba(23,84,140,.32),transparent 38rem),var(--navy); color:var(--paper); }
[data-testid="stAppViewContainer"]::after { content:"";position:fixed;inset:0;z-index:9999;pointer-events:none;opacity:.10;background:repeating-linear-gradient(to bottom,transparent 0,transparent 3px,rgba(93,228,255,.13) 4px); }
[data-testid="stHeader"] { background:rgba(5,10,36,.92);border-bottom:1px solid rgba(93,228,255,.25); }
[data-testid="stSidebar"] { background:#06102d;border-right:2px solid var(--cyan);box-shadow:8px 0 0 rgba(1,3,14,.6); }
[data-testid="stSidebar"] p,[data-testid="stSidebar"] label,[data-testid="stSidebar"] span,p,li,label { color:var(--paper); }
.block-container { max-width:1500px;padding-top:2.4rem;padding-bottom:4rem; }
h1,h2,h3,h4 { color:var(--cyan)!important;font-family:var(--mono)!important;letter-spacing:.02em;text-shadow:2px 2px 0 var(--shadow); }
h1::before { content:"C:\\> ";color:var(--amber); } h2::before,h3::before { content:">> ";color:var(--green); }
[data-testid="stCaptionContainer"] { color:var(--muted); }
div[data-testid="stMetric"] { min-height:112px;padding:1rem 1.1rem;background:linear-gradient(145deg,rgba(18,58,115,.76),rgba(7,20,58,.94));border:1px solid var(--cyan);border-left:5px solid var(--amber);box-shadow:5px 5px 0 var(--shadow); }
[data-testid="stMetricLabel"] { color:var(--muted);text-transform:uppercase; } [data-testid="stMetricValue"] { color:var(--amber); }
.stButton>button,.stDownloadButton>button { border-radius:0;border:2px solid var(--cyan);background:var(--blue);color:#fff;box-shadow:4px 4px 0 var(--shadow);text-transform:uppercase;font-family:var(--mono);font-weight:700; }
.stButton>button:hover,.stDownloadButton>button:hover { border-color:var(--amber);color:var(--amber);transform:translate(-1px,-1px);box-shadow:6px 6px 0 var(--shadow); }
.stButton>button:active,.stDownloadButton>button:active { transform:translate(3px,3px);box-shadow:1px 1px 0 var(--shadow); }
div[data-baseweb="select"]>div,div[data-baseweb="input"]>div,[data-testid="stNumberInput"] input,[data-testid="stTextInput"] input { border-radius:0!important;border-color:var(--cyan)!important;background:#03071d!important;color:var(--paper)!important; }
[data-baseweb="popover"],[data-baseweb="menu"] { background:var(--panel)!important; } [role="option"] { color:var(--paper)!important; } [role="option"]:hover,[aria-selected="true"] { background:var(--blue)!important; }
[data-testid="stDataFrame"],[data-testid="stTable"],[data-testid="stPlotlyChart"],[data-testid="stJson"] { border:1px solid rgba(93,228,255,.72);box-shadow:5px 5px 0 var(--shadow); }
[data-testid="stCodeBlock"] { border:1px solid var(--green);border-radius:0;box-shadow:5px 5px 0 var(--shadow); }
[data-testid="stAlert"] { border-radius:0;border:1px solid var(--cyan);border-left:6px solid var(--amber);background:rgba(18,58,115,.55);color:var(--paper); }
[data-baseweb="tab-list"] { gap:.35rem; } [data-baseweb="tab"] { border:1px solid var(--blue);border-radius:0;color:var(--paper); } [aria-selected="true"][data-baseweb="tab"] { border-color:var(--cyan);background:var(--blue);color:var(--amber); }
[data-testid="stSidebar"] [role="radiogroup"] label { margin-bottom:.35rem;padding:.45rem .55rem;border:1px solid transparent; } [data-testid="stSidebar"] [role="radiogroup"] label:hover { background:var(--blue);border-color:var(--cyan); }
hr { border-color:rgba(93,228,255,.32)!important; }
@media (prefers-reduced-motion:no-preference) { .dos-cursor { animation:blink 1.05s steps(1) infinite; } @keyframes blink { 50% { opacity:0; } } }
@media (max-width:700px) { .block-container { padding-left:1rem;padding-right:1rem; } div[data-testid="stMetric"] { min-height:94px; } }
</style>
"""


def configure_page() -> None:
    st.set_page_config(
        page_title="Thesis Data Observatory",
        page_icon="◫",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(RETRO_CSS, unsafe_allow_html=True)


def metric_bytes(label: str, value: int | float | None) -> None:
    display = humanize.naturalsize(value or 0, binary=True)
    st.metric(label, display)


def dataframe(frame: pd.DataFrame, *, height: int = 420) -> None:
    st.dataframe(frame, use_container_width=True, height=height, hide_index=True)


def path_caption(path: str | Path) -> None:
    st.caption(f"Path: `{path}`")


def error_box(exc: Exception) -> None:
    st.error(f"{type(exc).__name__}: {exc}")
