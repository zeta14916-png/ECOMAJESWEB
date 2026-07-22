"""Importar Compra de Productos — ECOMAJES ERP FASE 2.

Permite importar registros de compras de productos desde un archivo .xlsx.
NO modifica precios ni stock; solo registra la compra en la tabla ``compras``.

Columnas esperadas (case-insensitive, aliases):
  CODIGO / DESCRIPCION / CANTIDAD / COSTO UNITARIO / PROVEEDOR / FECHA
"""

from __future__ import annotations

import io
from datetime import date
from decimal import Decimal, InvalidOperation

import pandas as pd
import streamlit as st

from ecomajes import config, db

# Column aliases → canonical name
_COLUMN_ALIASES = {
    "codigo": "codigo",
    "código": "codigo",
    "cod": "codigo",
    "cod.": "codigo",
    "descripcion": "descripcion",
    "descripción": "descripcion",
    "desc": "descripcion",
    "producto": "descripcion",
    "nombre": "descripcion",
    "cantidad": "cantidad",
    "cant": "cantidad",
    "qty": "cantidad",
    "costo unitario": "costo_unitario",
    "costo_unitario": "costo_unitario",
    "costo": "costo_unitario",
    "precio compra": "costo_unitario",
    "precio_compra": "costo_unitario",
    "p. compra": "costo_unitario",
    "proveedor": "proveedor",
    "prove": "proveedor",
    "supplier": "proveedor",
    "fecha": "fecha",
    "date": "fecha",
    "fecha compra": "fecha",
}


def _cell(value) -> str:
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
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text


def _parse_decimal(value) -> Decimal | None:
    """Parse a cell value to Decimal, tolerating S/ prefix and commas."""
    raw = _cell(value)
    if not raw:
        return None
    raw = raw.replace("S/", "").replace(",", "").strip()
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def _parse_date(value) -> date | None:
    """Parse a cell value to date."""
    if isinstance(value, date):
        return value
    if hasattr(value, "date"):
        return value.date()
    raw = _cell(value)
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            import datetime
            return datetime.datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    """Rename columns to canonical names using the alias table."""
    rename: dict[str, str] = {}
    for col in df.columns:
        canon = _COLUMN_ALIASES.get(str(col).strip().lower())
        if canon:
            rename[col] = canon
    return df.rename(columns=rename)


def _build_template() -> bytes:
    """Return a minimal .xlsx template as bytes."""
    sample = pd.DataFrame(
        columns=["CODIGO", "DESCRIPCION", "CANTIDAD", "COSTO UNITARIO", "PROVEEDOR", "FECHA"]
    )
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        sample.to_excel(writer, index=False, sheet_name="Compras")
    return buf.getvalue()


def _parse_rows(uploaded_file) -> tuple[list[dict], list[str]]:
    """Parse the uploaded .xlsx and return (rows, warnings)."""
    warnings: list[str] = []
    try:
        sheets = pd.read_excel(uploaded_file, sheet_name=None, dtype=str)
    except Exception as exc:
        return [], [f"No se pudo leer el archivo: {exc}"]

    all_rows: list[dict] = []
    for sheet_name, df in sheets.items():
        df = _normalize_headers(df)
        for idx, row in df.iterrows():
            codigo = _cell(row.get("codigo"))
            descripcion = _cell(row.get("descripcion"))
            if not codigo and not descripcion:
                continue  # skip completely empty rows

            cantidad = _parse_decimal(row.get("cantidad"))
            costo_unitario = _parse_decimal(row.get("costo_unitario"))
            proveedor = _cell(row.get("proveedor")) or None
            fecha_val = _parse_date(row.get("fecha"))

            if cantidad is None or cantidad <= 0:
                warnings.append(
                    f"Fila {idx + 2} ({codigo or descripcion}): cantidad inválida, se usará 0."
                )
                cantidad = Decimal("0")
            if costo_unitario is None or costo_unitario < 0:
                warnings.append(
                    f"Fila {idx + 2} ({codigo or descripcion}): costo unitario inválido, se usará 0."
                )
                costo_unitario = Decimal("0")

            all_rows.append(
                {
                    "codigo": codigo or None,
                    "descripcion": descripcion,
                    "cantidad": cantidad,
                    "costo_unitario": costo_unitario,
                    "costo_total": costo_unitario * cantidad,
                    "proveedor": proveedor,
                    "fecha": fecha_val,
                }
            )

    return all_rows, warnings


def render(ctx: dict) -> None:
    st.header(ctx["title"])
    st.caption(ctx["breadcrumb"])

    st.info(
        "📥 **Importar Compra de Productos** — Registra compras realizadas a proveedores. "
        "Esta importación **NO modifica precios ni stock**; solo guarda el registro de compra."
    )

    # --- Sede selector ------------------------------------------------------ #
    sede_options = ctx.get("sede_options", [config.SEDE_PRINCIPAL, config.SEDE_SUCURSAL])
    if ctx["sede"] in sede_options:
        default_sede = ctx["sede"]
    else:
        default_sede = sede_options[0]
    sede = st.selectbox("Sede destino", sede_options, index=sede_options.index(default_sede))

    st.divider()

    # --- Template download -------------------------------------------------- #
    st.subheader("1. Descargar plantilla")
    st.caption("Descarga la plantilla Excel, complétala con los datos de compra y luego súbela.")
    template_bytes = _build_template()
    st.download_button(
        label="📄 Descargar plantilla (.xlsx)",
        data=template_bytes,
        file_name="plantilla_compra_productos.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.divider()

    # --- Upload ------------------------------------------------------------- #
    st.subheader("2. Subir archivo")
    uploaded = st.file_uploader(
        "Selecciona el archivo Excel (.xlsx)",
        type=["xlsx"],
        help="El archivo debe tener las columnas: CODIGO, DESCRIPCION, CANTIDAD, COSTO UNITARIO, PROVEEDOR (opt.), FECHA (opt.)",
    )

    if uploaded is None:
        st.caption("Sube el archivo para continuar.")
        return

    rows, warnings = _parse_rows(uploaded)

    if warnings:
        with st.expander(f"⚠️ {len(warnings)} advertencia(s) de formato"):
            for w in warnings:
                st.caption(f"• {w}")

    if not rows:
        st.error("No se encontraron filas válidas en el archivo.")
        return

    st.divider()

    # --- Preview ------------------------------------------------------------ #
    st.subheader("3. Vista previa y validación")
    st.caption(f"Se encontraron **{len(rows)}** filas listas para importar.")

    preview_rows = [
        {
            "Código": r["codigo"] or "—",
            "Descripción": r["descripcion"] or "—",
            "Cantidad": float(r["cantidad"]),
            "Costo unitario": float(r["costo_unitario"]),
            "Costo total": float(r["costo_total"]),
            "Proveedor": r["proveedor"] or "—",
            "Fecha": str(r["fecha"]) if r["fecha"] else "—",
        }
        for r in rows
    ]
    st.dataframe(preview_rows, use_container_width=True, hide_index=True)

    total_compra = sum(float(r["costo_total"]) for r in rows)
    st.metric("Total de la compra", f"$ {total_compra:,.2f}")

    st.divider()

    # --- Confirm dialog ----------------------------------------------------- #
    st.subheader("4. Registrar compra")

    @st.dialog("Confirmar importación de compra")
    def _confirm_dialog() -> None:
        st.markdown(f"**Filas a registrar:** {len(rows)}")
        st.markdown(f"**Sede:** {sede}")
        st.markdown(f"**Total de compra:** $ {total_compra:,.2f}")
        st.warning("Esta acción registrará la compra. NO modifica precios ni stock.")
        col_c, col_ok = st.columns(2)
        with col_c:
            if st.button("❌ Cancelar", use_container_width=True):
                st.rerun()
        with col_ok:
            if st.button("✅ Registrar compra", use_container_width=True, type="primary"):
                try:
                    result = db.register_purchase_import(
                        rows=rows,
                        sede=sede,
                        usuario_rol=ctx["usuario_rol"],
                    )
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Error al importar: {exc}")
                    return

                st.session_state["compra_import_result"] = result
                db.log_audit(
                    db.AUDIT_IMPORT,
                    "Importar Compra",
                    detalle=(
                        f"Sede: {sede} · Filas: {len(rows)} · "
                        f"Registradas: {result['inserted']} · "
                        f"Errores: {result['errors']}"
                    ),
                    usuario_rol=ctx["usuario_rol"],
                    sede=sede,
                )
                st.rerun()

    # Show result if just imported
    result = st.session_state.pop("compra_import_result", None)
    if result:
        st.success(
            f"✅ Importación completada: **{result['inserted']}** registros guardados · "
            f"**{result['errors']}** errores."
        )
        if result.get("error_details"):
            with st.expander("Ver errores"):
                for e in result["error_details"]:
                    st.caption(f"• {e}")

    if st.button("📥 Registrar compra", type="primary", use_container_width=True):
        _confirm_dialog()

    st.divider()

    # --- Historial de compras ------------------------------------------------ #
    st.subheader("📋 Historial de compras")
    hist = db.list_purchases(
        sede=ctx["sede"] if ctx["sede"] in [config.SEDE_PRINCIPAL, config.SEDE_SUCURSAL] else None,
        include_all_sedes=ctx.get("include_all_sedes", False),
        limit=100,
    )
    if hist:
        hist_rows = [
            {
                "Fecha registro": h["created_at"].strftime("%Y-%m-%d %H:%M"),
                "Fecha compra": str(h["fecha"]) if h["fecha"] else "—",
                "Código": h["codigo"] or "—",
                "Descripción": h["descripcion"],
                "Cantidad": float(h["cantidad"]),
                "Costo unit.": float(h["costo_unitario"]),
                "Costo total": float(h["costo_total"]),
                "Proveedor": h["proveedor"] or "—",
                "Sede": h["sede"],
            }
            for h in hist
        ]
        st.dataframe(hist_rows, use_container_width=True, hide_index=True)
    else:
        st.caption("Aún no hay compras registradas.")
