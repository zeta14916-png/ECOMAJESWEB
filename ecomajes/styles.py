"""Estilos visuales centralizados para ECOMAJES ERP.

Inyecta el CSS de marca una sola vez desde app.py.
No modifica lógica, estructura ni funcionalidad.
"""

import base64
from pathlib import Path

import streamlit as st

# ── Paleta de colores ECOMAJES ──────────────────────────────────────────────
AZUL_PROFUNDO   = "#0047A1"
AZUL_ACERO      = "#1565C0"
VERDE           = "#2E7D32"
BLANCO          = "#FFFFFF"
GRIS_METALICO   = "#B0BEC5"
GRIS_GRAFITO    = "#263338"
GRIS_FONDO      = "#F5F7FA"
GRIS_BORDE      = "#DDE3EA"
TEXTO_PRINCIPAL = "#1A2332"
TEXTO_SECUNDARIO= "#546E7A"

# Estado semáforo
ROJO_CRITICO    = "#D32F2F"
AMARILLO_BAJO   = "#F57F17"
VERDE_DISPONIBLE= "#2E7D32"

LOGO_PATH = Path(__file__).parent.parent / "assets" / "logo_ecomajes.png"


def _logo_b64() -> str:
    """Devuelve el logo en base64 para incrustar en HTML."""
    try:
        data = LOGO_PATH.read_bytes()
        return base64.b64encode(data).decode()
    except Exception:
        return ""


def _css() -> str:
    return f"""
<style>
/* ══════════════════════════════════════════════════════════
   ECOMAJES ERP — CSS Global de Marca
   Paleta: Azul Profundo · Azul Acero · Verde · Gris Metálico
   ══════════════════════════════════════════════════════════ */

/* ── Tipografía base ──────────────────────────────────────── */
html, body, [class*="css"] {{
    font-family: 'Segoe UI', 'Inter', 'Helvetica Neue', Arial, sans-serif;
    color: {TEXTO_PRINCIPAL};
}}

/* ── Fondo general ────────────────────────────────────────── */
.stApp {{
    background-color: {GRIS_FONDO};
}}
.block-container {{
    padding-top: 1.5rem !important;
    padding-bottom: 2rem !important;
    max-width: 1280px;
}}

/* ── SIDEBAR ──────────────────────────────────────────────── */
section[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, {GRIS_GRAFITO} 0%, #1a2632 100%) !important;
    border-right: 2px solid {AZUL_ACERO};
}}
section[data-testid="stSidebar"] * {{
    color: {BLANCO} !important;
}}
section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] .stCaption p {{
    color: {GRIS_METALICO} !important;
    font-size: 0.82rem;
}}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {{
    color: {BLANCO} !important;
    font-size: 1.1rem;
    font-weight: 700;
    letter-spacing: 0.02em;
}}
/* Separador sidebar */
section[data-testid="stSidebar"] hr {{
    border-color: rgba(176,190,197,0.25) !important;
    margin: 0.6rem 0;
}}
/* Botones del menú lateral */
section[data-testid="stSidebar"] .stButton > button {{
    background: rgba(255,255,255,0.07) !important;
    color: {BLANCO} !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    border-radius: 8px !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    text-align: left !important;
    padding: 0.45rem 0.75rem !important;
    margin-bottom: 2px !important;
    transition: all 0.15s ease !important;
}}
section[data-testid="stSidebar"] .stButton > button:hover {{
    background: rgba(21,101,192,0.35) !important;
    border-color: {AZUL_ACERO} !important;
    transform: translateX(3px);
}}
/* Botón cerrar sesión */
section[data-testid="stSidebar"] .stButton:last-of-type > button {{
    background: rgba(211,47,47,0.18) !important;
    border-color: rgba(211,47,47,0.4) !important;
    color: #FF8A80 !important;
    margin-top: 0.5rem !important;
}}
section[data-testid="stSidebar"] .stButton:last-of-type > button:hover {{
    background: rgba(211,47,47,0.35) !important;
}}
/* Expanders del sidebar */
section[data-testid="stSidebar"] [data-testid="stExpander"] {{
    border: none !important;
    background: transparent !important;
}}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary {{
    background: rgba(255,255,255,0.05) !important;
    border-radius: 8px !important;
    padding: 0.4rem 0.6rem !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    color: {GRIS_METALICO} !important;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    border: 1px solid rgba(255,255,255,0.08) !important;
    margin-bottom: 3px;
}}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {{
    background: rgba(21,101,192,0.2) !important;
    color: {BLANCO} !important;
}}

/* ── ENCABEZADOS PRINCIPALES ──────────────────────────────── */
h1 {{
    color: {AZUL_PROFUNDO} !important;
    font-weight: 800 !important;
    font-size: 1.7rem !important;
    letter-spacing: -0.01em;
    border-bottom: 3px solid {AZUL_ACERO};
    padding-bottom: 0.4rem;
    margin-bottom: 0.3rem !important;
}}
h2 {{
    color: {AZUL_PROFUNDO} !important;
    font-weight: 700 !important;
    font-size: 1.25rem !important;
}}
h3 {{
    color: {AZUL_ACERO} !important;
    font-weight: 600 !important;
    font-size: 1.05rem !important;
}}
/* Caption / breadcrumb */
.stCaption p {{
    color: {TEXTO_SECUNDARIO} !important;
    font-size: 0.82rem !important;
}}

/* ── BOTONES PRINCIPALES ──────────────────────────────────── */
.stButton > button[kind="primary"],
.stFormSubmitButton > button[kind="primary"] {{
    background: linear-gradient(135deg, {AZUL_ACERO}, {AZUL_PROFUNDO}) !important;
    color: {BLANCO} !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    letter-spacing: 0.02em;
    box-shadow: 0 2px 8px rgba(21,101,192,0.3);
    transition: all 0.18s ease !important;
}}
.stButton > button[kind="primary"]:hover,
.stFormSubmitButton > button[kind="primary"]:hover {{
    background: linear-gradient(135deg, {AZUL_PROFUNDO}, #00338D) !important;
    box-shadow: 0 4px 14px rgba(21,101,192,0.45) !important;
    transform: translateY(-1px);
}}
/* Botones secundarios */
.stButton > button:not([kind="primary"]),
.stFormSubmitButton > button:not([kind="primary"]) {{
    background: {BLANCO} !important;
    color: {AZUL_ACERO} !important;
    border: 1.5px solid {GRIS_BORDE} !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    transition: all 0.15s ease !important;
}}
.stButton > button:not([kind="primary"]):hover,
.stFormSubmitButton > button:not([kind="primary"]):hover {{
    border-color: {AZUL_ACERO} !important;
    background: rgba(21,101,192,0.06) !important;
}}

/* ── FORMULARIOS ──────────────────────────────────────────── */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stSelectbox > div > div,
.stTextArea > div > textarea,
.stDateInput > div > div > input {{
    border: 1.5px solid {GRIS_BORDE} !important;
    border-radius: 8px !important;
    background: {BLANCO} !important;
    color: {TEXTO_PRINCIPAL} !important;
    transition: border-color 0.15s ease;
}}
.stTextInput > div > div > input:focus,
.stNumberInput > div > div > input:focus,
.stTextArea > div > textarea:focus {{
    border-color: {AZUL_ACERO} !important;
    box-shadow: 0 0 0 3px rgba(21,101,192,0.12) !important;
}}
/* Etiquetas de campos */
.stTextInput label, .stNumberInput label, .stSelectbox label,
.stTextArea label, .stDateInput label, .stRadio label span,
.stCheckbox label span {{
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    color: {TEXTO_PRINCIPAL} !important;
    letter-spacing: 0.01em;
}}
/* Form container */
[data-testid="stForm"] {{
    background: {BLANCO};
    border: 1px solid {GRIS_BORDE};
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    margin-bottom: 1rem;
}}

/* ── TABLAS / DATAFRAMES ─────────────────────────────────── */
[data-testid="stDataFrame"] {{
    border-radius: 10px !important;
    overflow: hidden !important;
    border: 1px solid {GRIS_BORDE} !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.07);
}}
/* Header del dataframe */
[data-testid="stDataFrame"] th {{
    background: {AZUL_PROFUNDO} !important;
    color: {BLANCO} !important;
    font-weight: 700 !important;
    font-size: 0.83rem !important;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    padding: 0.6rem 0.8rem !important;
    border: none !important;
}}
/* Filas */
[data-testid="stDataFrame"] tr:nth-child(even) td {{
    background: #F0F4FA !important;
}}
[data-testid="stDataFrame"] tr:nth-child(odd) td {{
    background: {BLANCO} !important;
}}
[data-testid="stDataFrame"] td {{
    font-size: 0.87rem !important;
    padding: 0.5rem 0.8rem !important;
    border-bottom: 1px solid #EEF1F6 !important;
    color: {TEXTO_PRINCIPAL} !important;
}}
[data-testid="stDataFrame"] tr:hover td {{
    background: rgba(21,101,192,0.06) !important;
}}

/* ── MENSAJES ─────────────────────────────────────────────── */
[data-testid="stSuccess"] {{
    background: rgba(46,125,50,0.1) !important;
    border-left: 4px solid {VERDE} !important;
    border-radius: 8px !important;
    color: #1B5E20 !important;
}}
[data-testid="stError"] {{
    background: rgba(211,47,47,0.1) !important;
    border-left: 4px solid {ROJO_CRITICO} !important;
    border-radius: 8px !important;
    color: #B71C1C !important;
}}
[data-testid="stWarning"] {{
    background: rgba(245,127,23,0.1) !important;
    border-left: 4px solid {AMARILLO_BAJO} !important;
    border-radius: 8px !important;
    color: #E65100 !important;
}}
[data-testid="stInfo"] {{
    background: rgba(21,101,192,0.08) !important;
    border-left: 4px solid {AZUL_ACERO} !important;
    border-radius: 8px !important;
    color: {AZUL_PROFUNDO} !important;
}}

/* ── EXPANDERS (módulos) ─────────────────────────────────── */
[data-testid="stExpander"] {{
    border: 1px solid {GRIS_BORDE} !important;
    border-radius: 10px !important;
    background: {BLANCO} !important;
    margin-bottom: 0.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}}
[data-testid="stExpander"] summary {{
    font-weight: 600 !important;
    color: {AZUL_ACERO} !important;
    padding: 0.65rem 1rem !important;
}}
[data-testid="stExpander"] summary:hover {{
    background: rgba(21,101,192,0.04) !important;
    border-radius: 10px 10px 0 0 !important;
}}

/* ── DIVIDER ─────────────────────────────────────────────── */
hr {{
    border-color: {GRIS_BORDE} !important;
    margin: 0.75rem 0 !important;
}}

/* ── TABS ────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {{
    gap: 4px;
    background: {GRIS_FONDO};
    border-radius: 10px;
    padding: 4px;
}}
.stTabs [data-baseweb="tab"] {{
    border-radius: 8px !important;
    font-weight: 600 !important;
    color: {TEXTO_SECUNDARIO} !important;
    background: transparent !important;
    border: none !important;
    padding: 0.45rem 1.1rem !important;
}}
.stTabs [aria-selected="true"] {{
    background: {AZUL_ACERO} !important;
    color: {BLANCO} !important;
    box-shadow: 0 2px 6px rgba(21,101,192,0.3) !important;
}}

/* ── MÉTRICAS / CARDS ────────────────────────────────────── */
[data-testid="metric-container"] {{
    background: {BLANCO};
    border: 1px solid {GRIS_BORDE};
    border-radius: 12px;
    padding: 1rem 1.25rem;
    box-shadow: 0 1px 5px rgba(0,0,0,0.07);
    border-top: 3px solid {AZUL_ACERO};
}}
[data-testid="metric-container"] [data-testid="stMetricValue"] {{
    color: {AZUL_PROFUNDO} !important;
    font-weight: 800 !important;
    font-size: 1.6rem !important;
}}
[data-testid="metric-container"] [data-testid="stMetricLabel"] {{
    color: {TEXTO_SECUNDARIO} !important;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}}

/* ── RADIO BUTTONS (método de pago, etc.) ────────────────── */
.stRadio > div {{
    gap: 0.5rem;
    flex-direction: row;
    flex-wrap: wrap;
}}
.stRadio [data-testid="stMarkdownContainer"] p {{
    font-weight: 500;
}}

/* ── SCROLLBAR personalizada ─────────────────────────────── */
::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: {GRIS_FONDO}; }}
::-webkit-scrollbar-thumb {{ background: {GRIS_METALICO}; border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: {AZUL_ACERO}; }}

/* ── ENCABEZADO CUSTOM (header bar) ─────────────────────── */
.ecomajes-header {{
    display: flex;
    align-items: center;
    gap: 1rem;
    background: linear-gradient(90deg, {AZUL_PROFUNDO} 0%, {AZUL_ACERO} 100%);
    color: {BLANCO};
    padding: 0.65rem 1.25rem;
    border-radius: 12px;
    margin-bottom: 1.2rem;
    box-shadow: 0 2px 8px rgba(0,71,161,0.25);
}}
.ecomajes-header .eco-title {{
    font-size: 1.2rem; font-weight: 800; letter-spacing: 0.02em;
}}
.ecomajes-header .eco-slogan {{
    font-size: 0.75rem; color: rgba(255,255,255,0.75); font-style: italic;
}}
.ecomajes-header .eco-meta {{
    margin-left: auto; font-size: 0.82rem; color: rgba(255,255,255,0.85);
    text-align: right;
}}
.ecomajes-header .eco-badge {{
    background: rgba(255,255,255,0.15);
    border-radius: 20px;
    padding: 0.18rem 0.7rem;
    font-size: 0.75rem;
    font-weight: 600;
    border: 1px solid rgba(255,255,255,0.25);
    margin-left: 0.4rem;
}}
</style>
"""


def inject_global_css() -> None:
    """Inyecta el CSS global de ECOMAJES. Llamar una vez desde app.py."""
    st.markdown(_css(), unsafe_allow_html=True)


def logo_b64_img(width: int = 60) -> str:
    """Retorna un tag <img> con el logo en base64."""
    b64 = _logo_b64()
    if not b64:
        return ""
    return f'<img src="data:image/png;base64,{b64}" width="{width}" style="border-radius:50%;object-fit:contain;" />'
