"""Auditoría view for ECOMAJES ERP (GERENCIA only).

Read-only trail of important actions recorded across the app: logins, product
create/edit/deactivate, price changes, inventory movements, sale-report
generation, expenses and payroll payments. Entries are written best-effort by
the features themselves via ``db.log_audit`` (a failure to log never breaks the
underlying action).

Fields shown: Fecha, Usuario, Rol, Acción, Módulo, Detalles. The app logs in by
role, so "Usuario" and "Rol" are the same value (the acting role).
"""

from datetime import date, timedelta

import streamlit as st

from ecomajes import config, db


def _action_label(key: str) -> str:
    return db.AUDIT_ACTION_LABELS.get(key, key)


def _filters() -> tuple:
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        accion = st.selectbox(
            "Acción",
            [None, *db.AUDIT_ACTION_LABELS.keys()],
            format_func=lambda k: "Todas" if k is None else _action_label(k),
        )
    with col2:
        modulos = db.list_audit_modules()
        modulo = st.selectbox(
            "Módulo",
            [None, *modulos],
            format_func=lambda m: "Todos" if m is None else m,
        )
    with col3:
        date_from = st.date_input(
            "Desde", value=date.today() - timedelta(days=30), key="audit_from"
        )
    with col4:
        date_to = st.date_input("Hasta", value=date.today(), key="audit_to")
    return accion, modulo, date_from, date_to


def render(ctx: dict) -> None:
    st.header(ctx["title"])
    st.caption(ctx["breadcrumb"])

    # Defensive guard: this module is wired only to the GERENCIA menu, but keep
    # the check in case the route is ever reused.
    if ctx["usuario_rol"] != config.ROLE_GERENCIA:
        st.error("Acceso restringido a GERENCIA.")
        return

    st.write(
        "Registro de acciones importantes del sistema. Solo lectura."
    )

    accion, modulo, date_from, date_to = _filters()

    entries = db.list_audit(
        accion=accion,
        modulo=modulo,
        date_from=date_from or None,
        date_to=date_to or None,
    )

    if not entries:
        st.caption("No hay registros de auditoría para el filtro seleccionado.")
        return

    rows = [
        {
            "Fecha": e["created_at"].strftime("%Y-%m-%d %H:%M"),
            "Usuario": e["usuario_rol"] or "—",
            "Rol": e["usuario_rol"] or "—",
            "Acción": _action_label(e["accion"]),
            "Módulo": e["modulo"],
            "Detalles": e["detalle"] or "—",
        }
        for e in entries
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.caption(f"{len(rows)} registro(s).")
