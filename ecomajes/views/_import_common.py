"""Shared UI for the GERENCIA import modules (Productos / Precios / Stock).

All three importers use the same product/price backup safety net
(`product_backups`), so the backup status panel and the restore confirmation
dialog live here and are reused by each view. Keeping a single implementation
means a restore always reverts the whole catalog + stock + prices the same way,
no matter which import page triggered it.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ecomajes import config, db


def cell(value) -> str:
    """Normalize a spreadsheet cell to a trimmed string ('' for NaN/None)."""
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    # Whole-number floats come back as "123.0"; drop the trailing ".0".
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text


@st.dialog("Restaurar inventario")
def restore_dialog(backup: dict, usuario_rol: str, modulo: str) -> None:
    """Confirmation modal for restoring the last backup (GERENCIA)."""
    st.warning(
        "Estás a punto de restaurar el inventario anterior. Se perderán "
        "todos los cambios posteriores a ese respaldo."
    )
    when = backup["created_at"].strftime("%d/%m/%Y %H:%M")
    st.caption(f"Respaldo del {when} · {backup['product_count']} productos")

    b1, b2 = st.columns(2)
    if b1.button("❌ Cancelar", use_container_width=True):
        st.rerun()
    if b2.button("♻️ Restaurar", type="primary", use_container_width=True):
        db.restore_products_backup(backup["id"])
        db.log_audit(
            db.AUDIT_IMPORT,
            modulo,
            detalle=(
                f"Inventario restaurado desde respaldo #{backup['id']} "
                f"({backup['product_count']} productos)"
            ),
            usuario_rol=usuario_rol,
        )
        st.session_state["restore_done"] = True
        st.rerun()


def render_backup_panel(ctx: dict, modulo: str) -> None:
    """GERENCIA-only backup status + Restaurar último respaldo button.

    `modulo` is the audit-log module label for a restore triggered here.
    """
    if ctx.get("usuario_rol") != config.ROLE_GERENCIA:
        return

    if st.session_state.pop("restore_done", False):
        st.success("Inventario restaurado correctamente.")

    last = db.get_last_backup()
    with st.container(border=True):
        st.markdown("**🛟 Respaldo del inventario**")
        if last:
            when = last["created_at"].strftime("%d/%m/%Y %H:%M")
            modo = db.IMPORT_MODE_LABELS.get(
                last["import_mode"], last["import_mode"]
            )
            st.caption(
                f"Último respaldo: {when} · Modo: {modo} · "
                f"Productos: {last['product_count']}"
            )
        else:
            st.caption(
                "Aún no hay respaldos. Se crea uno automáticamente antes de "
                "cada importación."
            )
        if st.button(
            "♻️ Restaurar último respaldo",
            disabled=last is None,
            help=(
                "Devuelve el catálogo de productos, stock y precios al estado "
                "del último respaldo."
            ),
        ):
            restore_dialog(last, ctx["usuario_rol"], modulo)
