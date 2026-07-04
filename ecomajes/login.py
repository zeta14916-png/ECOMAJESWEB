"""Login flow for ECOMAJES ERP.

Two steps:

1. `render_login` — select the role and (when required) enter the password.
   Location/scope options are never shown here, so they cannot be seen before
   the correct password is entered.
2. `render_scope_selection` — shown only after a successful login; the user
   picks the location/scope. GERENCIA additionally sees the consolidated
   "Empresa Completa" scope.
"""

import streamlit as st

from ecomajes import auth, config, session


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
            st.rerun()
        else:
            st.error("Contraseña incorrecta.")


def render_scope_selection() -> None:
    role = session.current_role()

    st.title("ECOMAJES ERP")
    st.caption("Sistema de gestión — Acero y Ferretería")
    st.divider()

    st.subheader("Selección de ámbito")
    st.caption(f"Rol: {role}")

    scope_label = "Ámbito" if role == config.ROLE_GERENCIA else "Sede"
    sede = st.radio(scope_label, config.get_sedes(role))

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Continuar", type="primary", use_container_width=True):
            session.set_scope(sede)
            st.rerun()
    with col2:
        if st.button("Cancelar", use_container_width=True):
            session.logout()
            st.rerun()
