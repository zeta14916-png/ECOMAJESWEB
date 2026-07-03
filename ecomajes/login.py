"""Login screen for ECOMAJES ERP.

Renders the role selection, sede selection and (when required) password entry.
On success it stores the session and reruns into the main application.
"""

import streamlit as st

from ecomajes import auth, config, session


def render_login() -> None:
    st.title("ECOMAJES ERP")
    st.caption("Sistema de gestión — Acero y Ferretería")
    st.divider()

    st.subheader("Ingreso")

    role = st.selectbox("Rol", config.ROLES, index=0)
    sede = st.radio("Sede", config.SEDES, horizontal=True)

    password = ""
    if auth.requires_password(role):
        password = st.text_input("Contraseña", type="password")

    if st.button("Ingresar", type="primary", use_container_width=True):
        if auth.verify_password(role, password):
            session.login(role, sede)
            st.rerun()
        else:
            st.error("Contraseña incorrecta.")
