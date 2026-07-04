"""Login flow for ECOMAJES ERP.

Two steps:

1. `render_login` — select the role and (when required) enter the password.
   Location/scope options are never shown here, so they cannot be seen before
   the correct password is entered.
2. `render_scope_selection` — shown only after a successful login; the user
   picks the location/scope from a card layout. GERENCIA additionally sees the
   consolidated "Empresa Completa" scope.
"""

import streamlit as st

from ecomajes import auth, config, db, session

# UI-only session key holding the card the user has highlighted before
# confirming with "Continuar". This is presentation state, not auth state.
_PENDING_KEY = "scope_pending"

# Presentation metadata per scope (icon, copy, ECOMAJES accent color).
_SCOPE_META = {
    config.SEDE_PRINCIPAL: {
        "slug": "principal",
        "icon": "🏢",
        "title": "SEDE PRINCIPAL",
        "desc": "Administrar únicamente la sede principal.",
        "color": "#2E7D32",
        "tint": "rgba(46, 125, 50, 0.08)",
        "ring": "rgba(46, 125, 50, 0.35)",
    },
    config.SEDE_SUCURSAL: {
        "slug": "sucursal",
        "icon": "🏬",
        "title": "SUCURSAL",
        "desc": "Administrar únicamente la sucursal.",
        "color": "#1565C0",
        "tint": "rgba(21, 101, 192, 0.08)",
        "ring": "rgba(21, 101, 192, 0.35)",
    },
    config.SEDE_EMPRESA_COMPLETA: {
        "slug": "empresa",
        "icon": "🌎",
        "title": "EMPRESA COMPLETA",
        "desc": "Visualizar y administrar toda la empresa.",
        "color": "#424242",
        "tint": "rgba(66, 66, 66, 0.08)",
        "ring": "rgba(66, 66, 66, 0.35)",
    },
}


def render_login() -> None:
    st.title("ECOMAJES ERP")
    st.caption("Sistema de gestión — Acero y Ferretería")
    st.divider()

    st.subheader("Ingreso")

    role = st.selectbox("Rol", config.ROLES, index=0)

    password = ""
    if auth.requires_password(role):
        password = st.text_input("Contraseña", type="password")

    if st.button("Ingresar", type="primary", use_container_width=True):
        if auth.verify_password(role, password):
            session.authenticate(role)
            db.log_audit(
                db.AUDIT_LOGIN,
                "Autenticación",
                detalle=f"Ingreso como {role}",
                usuario_rol=role,
            )
            st.rerun()
        else:
            st.error("Contraseña incorrecta.")


def _scope_css(selected_meta: dict) -> str:
    """Global CSS for the scope cards; highlights the selected card."""
    return f"""
    <style>
    .scope-hero {{ text-align: center; margin: 0.5rem 0 1.75rem; }}
    .scope-hero h1 {{
        font-size: 2rem; font-weight: 800; color: #1a1a1a;
        letter-spacing: -0.01em; margin: 0 0 0.4rem;
    }}
    .scope-hero p {{ font-size: 1.02rem; color: #6b7280; margin: 0; }}

    /* Card buttons -------------------------------------------------------- */
    [class*="st-key-scope_card_"] button {{
        min-height: 210px;
        border: 2px solid #e5e7eb;
        border-radius: 18px;
        background: #ffffff;
        padding: 1.75rem 1.25rem;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease, background .18s ease;
    }}
    [class*="st-key-scope_card_"] button:hover {{
        transform: translateY(-4px);
        box-shadow: 0 10px 24px rgba(0, 0, 0, 0.10);
    }}
    [class*="st-key-scope_card_"] button:focus:not(:active) {{
        border-color: #d1d5db; box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }}
    [class*="st-key-scope_card_"] button [data-testid="stMarkdownContainer"] p {{
        margin: 0.28rem 0; text-align: center;
    }}
    [class*="st-key-scope_card_"] button [data-testid="stMarkdownContainer"] p:nth-child(1) {{
        font-size: 2.9rem; line-height: 1;
    }}
    [class*="st-key-scope_card_"] button [data-testid="stMarkdownContainer"] p:nth-child(2) {{
        font-size: 1.08rem; font-weight: 700; letter-spacing: 0.04em; color: #111827;
    }}
    [class*="st-key-scope_card_"] button [data-testid="stMarkdownContainer"] p:nth-child(3) {{
        font-size: 0.86rem; font-weight: 400; color: #6b7280; line-height: 1.4;
    }}

    /* Per-card hover accent ---------------------------------------------- */
    .st-key-scope_card_principal button:hover {{ border-color: #2E7D32; }}
    .st-key-scope_card_sucursal button:hover {{ border-color: #1565C0; }}
    .st-key-scope_card_empresa button:hover {{ border-color: #424242; }}

    /* Selected card ------------------------------------------------------- */
    .st-key-scope_card_{selected_meta['slug']} button {{
        border-color: {selected_meta['color']} !important;
        background: {selected_meta['tint']} !important;
        box-shadow: 0 0 0 3px {selected_meta['ring']}, 0 10px 24px rgba(0,0,0,0.08) !important;
    }}

    /* Action buttons ------------------------------------------------------ */
    .st-key-scope_continuar button {{
        background: #2E7D32; color: #ffffff; border: none;
        border-radius: 12px; font-weight: 600; padding: 0.65rem 0;
    }}
    .st-key-scope_continuar button:hover {{ background: #256628; color: #ffffff; }}
    .st-key-scope_cancelar button {{
        background: #ffffff; color: #424242; border: 1.5px solid #d1d5db;
        border-radius: 12px; font-weight: 600; padding: 0.65rem 0;
    }}
    .st-key-scope_cancelar button:hover {{ border-color: #424242; color: #424242; }}
    </style>
    """


def render_scope_selection() -> None:
    role = session.current_role()
    sedes = config.get_sedes(role)

    pending = st.session_state.get(_PENDING_KEY)
    if pending not in sedes:
        pending = sedes[0]
        st.session_state[_PENDING_KEY] = pending

    st.markdown(_scope_css(_SCOPE_META[pending]), unsafe_allow_html=True)

    st.markdown(
        "<div class='scope-hero'>"
        "<h1>¿Dónde desea trabajar hoy?</h1>"
        "<p>Seleccione el ámbito donde trabajará durante esta sesión.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    cols = st.columns(len(sedes), gap="large")
    for col, sede in zip(cols, sedes):
        meta = _SCOPE_META[sede]
        label = f"{meta['icon']}\n\n**{meta['title']}**\n\n{meta['desc']}"
        with col:
            if st.button(
                label,
                key=f"scope_card_{meta['slug']}",
                use_container_width=True,
            ):
                st.session_state[_PENDING_KEY] = sede
                st.rerun()

    st.write("")
    _, c_cont, c_canc, _ = st.columns([1, 1.3, 1.3, 1])
    with c_cont:
        if st.button(
            "Continuar", key="scope_continuar", use_container_width=True
        ):
            session.set_scope(st.session_state[_PENDING_KEY])
            st.session_state.pop(_PENDING_KEY, None)
            st.rerun()
    with c_canc:
        if st.button(
            "Cancelar", key="scope_cancelar", use_container_width=True
        ):
            st.session_state.pop(_PENDING_KEY, None)
            session.logout()
            st.rerun()
