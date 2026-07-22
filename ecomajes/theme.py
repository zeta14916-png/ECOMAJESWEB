"""ECOMAJES ERP — sistema de diseño global.

Paleta industrial: grafito / acero / blanco / azul acero / naranja industrial.
Inyectar con ``inject_css()`` una sola vez en app.py antes de renderizar.
No contiene lógica de negocio ni referencias a la BD.
"""

import streamlit as st

# --------------------------------------------------------------------------- #
# Tokens de color (un único lugar para cambiarlos)
# --------------------------------------------------------------------------- #
C_STEEL_BLUE  = "#1565C0"   # primario — azul acero
C_BLUE_HOVER  = "#0D47A1"   # hover de primario
C_ORANGE      = "#E65100"   # acento industrial / advertencia
C_ORANGE_HVR  = "#BF360C"
C_GREEN       = "#2E7D32"   # éxito
C_YELLOW      = "#F9A825"   # alerta
C_RED         = "#C62828"   # peligro / crítico

C_GRAPHITE    = "#1C2333"   # sidebar fondo
C_GRAPHITE2   = "#263044"   # sidebar hover
C_DIVIDER     = "#2D3A4F"   # separadores en sidebar
C_SIDEBAR_TXT = "#CBD5E1"   # texto sidebar inactivo
C_SIDEBAR_ACT = "#FFFFFF"   # texto sidebar activo

C_BG          = "#F8F9FB"   # fondo de página principal
C_CARD        = "#FFFFFF"   # tarjetas / contenedores
C_BORDER      = "#E2E8F0"   # bordes suaves
C_TEXT        = "#1A202C"   # texto principal
C_MUTED       = "#718096"   # texto secundario


_CSS = f"""
<style>
/* ═══════════════════════════════════════════════════
   1. PÁGINA PRINCIPAL
═══════════════════════════════════════════════════ */
.stApp {{
    background-color: {C_BG};
}}

/* Ocultar barra de menú de Streamlit (hamburguesa) */
#MainMenu {{ visibility: hidden; }}
footer {{ visibility: hidden; }}
[data-testid="stToolbar"] {{ visibility: hidden; right: 0; }}

/* ═══════════════════════════════════════════════════
   2. SIDEBAR — tema oscuro grafito
═══════════════════════════════════════════════════ */
[data-testid="stSidebar"] {{
    background-color: {C_GRAPHITE} !important;
    border-right: 1px solid {C_DIVIDER};
    min-width: 240px !important;
}}
[data-testid="stSidebar"] > div:first-child {{
    background-color: {C_GRAPHITE} !important;
}}

/* Todo el texto del sidebar */
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stMarkdown {{
    color: {C_SIDEBAR_TXT} !important;
}}
[data-testid="stSidebar"] h1 {{
    font-size: 1.15rem !important;
    font-weight: 700 !important;
    color: {C_SIDEBAR_ACT} !important;
    letter-spacing: 0.04em !important;
    text-transform: uppercase !important;
}}
[data-testid="stSidebar"] hr {{
    border-color: {C_DIVIDER} !important;
    margin: 0.6rem 0 !important;
}}

/* Botones de navegación en sidebar */
[data-testid="stSidebar"] .stButton > button {{
    background-color: transparent !important;
    color: {C_SIDEBAR_TXT} !important;
    border: none !important;
    border-radius: 8px !important;
    text-align: left !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    padding: 0.45rem 0.75rem !important;
    transition: background 0.15s ease, color 0.15s ease !important;
    box-shadow: none !important;
}}
[data-testid="stSidebar"] .stButton > button:hover {{
    background-color: {C_GRAPHITE2} !important;
    color: {C_SIDEBAR_ACT} !important;
}}

/* Expanders en sidebar (grupos de menú) */
[data-testid="stSidebar"] details {{
    border: none !important;
    background: transparent !important;
}}
[data-testid="stSidebar"] details summary {{
    color: {C_SIDEBAR_TXT} !important;
    font-size: 0.80rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.07em !important;
    text-transform: uppercase !important;
    padding: 0.4rem 0.5rem !important;
    background: transparent !important;
}}
[data-testid="stSidebar"] details summary:hover {{
    color: {C_SIDEBAR_ACT} !important;
}}
[data-testid="stSidebar"] details[open] summary {{
    color: {C_SIDEBAR_ACT} !important;
}}
[data-testid="stSidebar"] [data-testid="stExpanderDetails"] {{
    background: rgba(255,255,255,0.03) !important;
    border-left: 2px solid {C_DIVIDER} !important;
    margin-left: 0.5rem !important;
    padding-left: 0.25rem !important;
}}

/* Botón cerrar sesión — más visible */
[data-testid="stSidebar"] .st-key-logout_btn > button,
[data-testid="stSidebar"] .stButton:last-child > button {{
    color: #FDA4AF !important;
    font-size: 0.85rem !important;
    margin-top: 0.25rem !important;
}}
[data-testid="stSidebar"] .st-key-logout_btn > button:hover,
[data-testid="stSidebar"] .stButton:last-child > button:hover {{
    background-color: rgba(198,40,40,0.18) !important;
    color: #FCA5A5 !important;
}}

/* ═══════════════════════════════════════════════════
   3. ENCABEZADO DE PÁGINA
═══════════════════════════════════════════════════ */
.stApp h1 {{
    font-size: 1.6rem !important;
    font-weight: 700 !important;
    color: {C_TEXT} !important;
    letter-spacing: -0.01em !important;
    border-bottom: 2px solid {C_STEEL_BLUE} !important;
    padding-bottom: 0.4rem !important;
    margin-bottom: 0.25rem !important;
}}
.stApp h2 {{
    font-size: 1.15rem !important;
    font-weight: 600 !important;
    color: {C_TEXT} !important;
}}
.stApp h3 {{
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    color: {C_TEXT} !important;
}}

/* Caption / breadcrumb */
[data-testid="stCaptionContainer"] p {{
    color: {C_MUTED} !important;
    font-size: 0.80rem !important;
    letter-spacing: 0.01em !important;
}}

/* ═══════════════════════════════════════════════════
   4. BOTONES PRINCIPALES
═══════════════════════════════════════════════════ */

/* Botón primario (type="primary") */
.stButton > button[kind="primary"],
.stButton > button[data-testid="baseButton-primary"] {{
    background-color: {C_STEEL_BLUE} !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    letter-spacing: 0.02em !important;
    transition: background 0.15s ease !important;
}}
.stButton > button[kind="primary"]:hover,
.stButton > button[data-testid="baseButton-primary"]:hover {{
    background-color: {C_BLUE_HOVER} !important;
}}

/* Botón secundario normal (contenido principal, no sidebar) */
.stApp > [data-testid="stMain"] .stButton > button,
[data-testid="stForm"] .stButton > button {{
    background-color: {C_CARD} !important;
    color: {C_TEXT} !important;
    border: 1.5px solid {C_BORDER} !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    transition: border-color 0.15s ease, background 0.15s ease !important;
}}
.stApp > [data-testid="stMain"] .stButton > button:hover,
[data-testid="stForm"] .stButton > button:hover {{
    border-color: {C_STEEL_BLUE} !important;
    color: {C_STEEL_BLUE} !important;
}}

/* Botón de guardar / submit dentro de formularios */
[data-testid="stForm"] .stButton > button[kind="primary"],
[data-testid="stForm"] .stButton > button[data-testid="baseButton-primaryFormSubmit"] {{
    background-color: {C_STEEL_BLUE} !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}}
[data-testid="stForm"] .stButton > button[kind="primary"]:hover {{
    background-color: {C_BLUE_HOVER} !important;
}}

/* ═══════════════════════════════════════════════════
   5. INPUTS Y FORMULARIOS
═══════════════════════════════════════════════════ */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stSelectbox"] > div,
[data-testid="stNumberInput"] input {{
    border: 1.5px solid {C_BORDER} !important;
    border-radius: 6px !important;
    background-color: {C_CARD} !important;
    color: {C_TEXT} !important;
    font-size: 0.9rem !important;
    transition: border-color 0.15s ease !important;
}}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {{
    border-color: {C_STEEL_BLUE} !important;
    box-shadow: 0 0 0 3px rgba(21,101,192,0.12) !important;
}}

[data-testid="stForm"] {{
    background-color: {C_CARD} !important;
    border: 1px solid {C_BORDER} !important;
    border-radius: 12px !important;
    padding: 1.25rem !important;
}}

/* ═══════════════════════════════════════════════════
   6. DATAFRAME / TABLAS
═══════════════════════════════════════════════════ */
[data-testid="stDataFrame"] {{
    border: 1px solid {C_BORDER} !important;
    border-radius: 8px !important;
    overflow: hidden !important;
}}
[data-testid="stDataFrame"] th {{
    background-color: #EEF2F7 !important;
    color: {C_TEXT} !important;
    font-weight: 600 !important;
    font-size: 0.82rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
}}
[data-testid="stDataFrame"] td {{
    font-size: 0.88rem !important;
    color: {C_TEXT} !important;
}}

/* ═══════════════════════════════════════════════════
   7. MÉTRICAS / TARJETAS DE RESUMEN
═══════════════════════════════════════════════════ */
[data-testid="stMetric"] {{
    background-color: {C_CARD} !important;
    border: 1px solid {C_BORDER} !important;
    border-radius: 10px !important;
    padding: 1rem 1.25rem !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05) !important;
}}
[data-testid="stMetricLabel"] {{
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
    color: {C_MUTED} !important;
}}
[data-testid="stMetricValue"] {{
    color: {C_TEXT} !important;
    font-weight: 700 !important;
}}

/* ═══════════════════════════════════════════════════
   8. ALERTAS Y MENSAJES
═══════════════════════════════════════════════════ */
[data-testid="stSuccess"] {{
    background-color: rgba(46,125,50,0.10) !important;
    border-left: 4px solid {C_GREEN} !important;
    border-radius: 6px !important;
    color: #1B5E20 !important;
}}
[data-testid="stError"] {{
    background-color: rgba(198,40,40,0.10) !important;
    border-left: 4px solid {C_RED} !important;
    border-radius: 6px !important;
    color: #7F0000 !important;
}}
[data-testid="stWarning"] {{
    background-color: rgba(249,168,37,0.12) !important;
    border-left: 4px solid {C_YELLOW} !important;
    border-radius: 6px !important;
    color: #6D4C00 !important;
}}
[data-testid="stInfo"] {{
    background-color: rgba(21,101,192,0.08) !important;
    border-left: 4px solid {C_STEEL_BLUE} !important;
    border-radius: 6px !important;
    color: #0D3C7A !important;
}}

/* ═══════════════════════════════════════════════════
   9. EXPANDERS (contenido principal)
═══════════════════════════════════════════════════ */
[data-testid="stExpander"] {{
    border: 1px solid {C_BORDER} !important;
    border-radius: 8px !important;
    background-color: {C_CARD} !important;
}}
[data-testid="stExpander"] summary {{
    font-weight: 600 !important;
    color: {C_TEXT} !important;
}}

/* ═══════════════════════════════════════════════════
   10. TABS
═══════════════════════════════════════════════════ */
[data-testid="stTabs"] [role="tab"] {{
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    color: {C_MUTED} !important;
    border-bottom: 2px solid transparent !important;
}}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {{
    color: {C_STEEL_BLUE} !important;
    border-bottom-color: {C_STEEL_BLUE} !important;
}}

/* ═══════════════════════════════════════════════════
   11. DIVIDER
═══════════════════════════════════════════════════ */
hr {{
    border-color: {C_BORDER} !important;
    margin: 1rem 0 !important;
}}

/* ═══════════════════════════════════════════════════
   12. RADIO BUTTONS
═══════════════════════════════════════════════════ */
[data-testid="stRadio"] label {{
    font-size: 0.9rem !important;
    color: {C_TEXT} !important;
}}

/* ═══════════════════════════════════════════════════
   13. SELECTBOX
═══════════════════════════════════════════════════ */
[data-testid="stSelectbox"] label,
[data-testid="stTextInput"] label,
[data-testid="stTextArea"] label,
[data-testid="stNumberInput"] label {{
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    color: {C_TEXT} !important;
    letter-spacing: 0.02em !important;
}}

/* ═══════════════════════════════════════════════════
   14. CONTENEDORES CON BORDE (st.container(border=True))
═══════════════════════════════════════════════════ */
[data-testid="stVerticalBlockBorderWrapper"] {{
    border: 1px solid {C_BORDER} !important;
    border-radius: 10px !important;
    background-color: {C_CARD} !important;
    padding: 0.75rem 1rem !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
}}

/* ═══════════════════════════════════════════════════
   15. BANNER DE ENCABEZADO POR ROL
═══════════════════════════════════════════════════ */
.ecomajes-role-banner {{
    display: flex;
    align-items: center;
    gap: 1rem;
    background: linear-gradient(135deg, {C_GRAPHITE} 0%, #263044 100%);
    color: #FFFFFF;
    border-radius: 10px;
    padding: 0.75rem 1.25rem;
    margin-bottom: 1rem;
    border-left: 4px solid {C_STEEL_BLUE};
}}
.ecomajes-role-banner .banner-title {{
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: {C_SIDEBAR_TXT};
    margin: 0;
    line-height: 1;
}}
.ecomajes-role-banner .banner-role {{
    font-size: 1.05rem;
    font-weight: 700;
    color: #FFFFFF;
    margin: 0.2rem 0 0;
    line-height: 1;
}}
.ecomajes-role-banner .banner-sede {{
    font-size: 0.82rem;
    color: #94A3B8;
    margin: 0.15rem 0 0;
    line-height: 1;
}}
.ecomajes-role-banner .banner-icon {{
    font-size: 2rem;
    line-height: 1;
}}
</style>
"""


def inject_css() -> None:
    """Inyectar el CSS global de ECOMAJES una vez por sesión."""
    st.markdown(_CSS, unsafe_allow_html=True)


def role_banner(role: str, sede: str) -> None:
    """Mostrar un banner de contexto con el rol y sede activos."""
    icon_map = {
        "OPERARIOS": "🔧",
        "ÁREA ADMINISTRATIVA": "📋",
        "GERENCIA": "📊",
    }
    icon = icon_map.get(role, "🏭")
    scope_label = "Ámbito" if "GERENCIA" in role else "Sede"
    st.markdown(
        f"""
        <div class="ecomajes-role-banner">
            <span class="banner-icon">{icon}</span>
            <div>
                <p class="banner-title">ECOMAJES ERP</p>
                <p class="banner-role">{role}</p>
                <p class="banner-sede">{scope_label}: {sede}</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
