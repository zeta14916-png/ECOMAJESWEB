"""Intelligent Excel product importer (GERENCIA).

Upload an .xlsx/.xls file, preview the normalized rows, then import. Columns are
matched case-insensitively and may include: CODIGO, DESCRIPCION, UNIDAD, PRECIO
DE VENTA SOLES, COSTO INICIAL SOLES, FAMILIA, CATEGORIA.

Rules:
- Código must be unique; repeated códigos in the file are collapsed into one
  (keeping the clearest/fullest description) and reported as skipped duplicates.
- If a código already exists it updates the product; otherwise it is created.
- Missing categoría is auto-classified from the description; missing unidad
  defaults to "UNIDAD"; stock defaults to 0.

This module only writes products; it never touches the prices module/table.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ecomajes import config, db

# Spreadsheet header -> canonical field. Keys are lower-cased + stripped.
_COLUMN_ALIASES = {
    "codigo": "codigo",
    "código": "codigo",
    "cod": "codigo",
    "cod.": "codigo",
    "descripcion": "descripcion",
    "descripción": "descripcion",
    "desc": "descripcion",
    "producto": "descripcion",
    "unidad": "unidad",
    "und": "unidad",
    "um": "unidad",
    "u.m.": "unidad",
    "precio de venta soles": "precio_venta",
    "precio venta": "precio_venta",
    "precio": "precio_venta",
    "costo inicial soles": "costo",
    "costo": "costo",
    "familia": "familia",
    "categoria": "categoria",
    "categoría": "categoria",
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
    # Whole-number floats come back as "123.0"; drop the trailing ".0".
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text


def _parse(file) -> list[dict]:
    """Read the uploaded workbook into canonical row dicts."""
    df = pd.read_excel(file)
    rename = {}
    for col in df.columns:
        canon = _COLUMN_ALIASES.get(str(col).strip().lower())
        if canon:
            rename[col] = canon
    df = df.rename(columns=rename)

    records: list[dict] = []
    for _, r in df.iterrows():
        row = {
            "codigo": _cell(r.get("codigo")),
            "descripcion": _cell(r.get("descripcion")),
            "unidad": _cell(r.get("unidad")),
            "categoria": _cell(r.get("categoria")),
        }
        if row["codigo"] or row["descripcion"]:
            records.append(row)
    return records


def _dedupe(records: list[dict]) -> tuple[list[dict], int]:
    """Collapse repeated códigos, keeping the fullest description.

    Returns (deduped_rows, skipped_duplicates).
    """
    by_code: dict[str, dict] = {}
    order: list[str] = []
    no_code: list[dict] = []
    skipped = 0

    for r in records:
        code = r["codigo"]
        if not code:
            no_code.append(dict(r))
            continue
        if code in by_code:
            skipped += 1
            existing = by_code[code]
            existing["descripcion"] = db._fullest(
                existing["descripcion"], r["descripcion"]
            )
            for f in ("unidad", "categoria"):
                if not existing.get(f) and r.get(f):
                    existing[f] = r[f]
        else:
            by_code[code] = dict(r)
            order.append(code)

    deduped = [by_code[c] for c in order] + no_code
    return deduped, skipped


def _preview_rows(rows: list[dict]) -> list[dict]:
    """Shape deduped rows for the on-screen preview (with defaults applied)."""
    out = []
    for r in rows:
        categoria = r.get("categoria") or ""
        if categoria:
            cat_display = categoria
        else:
            cat_display = f"{db.classify_categoria(r['descripcion'])} (auto)"
        out.append(
            {
                "Código": r.get("codigo") or "—",
                "Descripción": r.get("descripcion") or "—",
                "Categoría": cat_display,
                "Unidad": r.get("unidad") or "UNIDAD",
                "Stock": 0,
            }
        )
    return out


def render(ctx: dict) -> None:
    st.header(ctx["title"])
    st.caption(ctx["breadcrumb"])

    st.markdown(
        "Sube un archivo **Excel** con tus productos. El sistema limpia los "
        "datos, evita duplicar códigos y clasifica la categoría "
        "automáticamente cuando falta."
    )
    with st.expander("¿Qué columnas puede tener el Excel?"):
        st.markdown(
            "- **CODIGO** (obligatorio para actualizar productos existentes)\n"
            "- **DESCRIPCION**\n"
            "- **UNIDAD** (si falta, se usa «UNIDAD»)\n"
            "- **CATEGORIA** (si falta, se clasifica desde la descripción)\n"
            "- PRECIO DE VENTA SOLES, COSTO INICIAL SOLES, FAMILIA "
            "(se leen pero no se importan aquí)\n\n"
            "El stock inicial se registra en **0**. Usa Registro de "
            "Movimiento para cargar existencias."
        )

    # --- Destino del import ------------------------------------------------ #
    col1, col2 = st.columns(2)
    with col1:
        default_sede = (
            ctx["sede"]
            if ctx["sede"] in (config.SEDE_PRINCIPAL, config.SEDE_SUCURSAL)
            else config.SEDE_PRINCIPAL
        )
        sede_options = [config.SEDE_PRINCIPAL, config.SEDE_SUCURSAL]
        sede_destino = st.selectbox(
            "Sede destino (para productos nuevos)",
            sede_options,
            index=sede_options.index(default_sede),
            help=(
                "Los productos nuevos se crean en esta sede. Si un código ya "
                "existe, se actualiza donde esté."
            ),
        )
    with col2:
        tipo_destino = st.selectbox(
            "Tipo de material (para productos nuevos)",
            [db.TIPO_NUEVO, db.TIPO_SEGUNDO_USO],
            format_func=lambda t: db.TIPO_LABELS[t],
        )

    uploaded = st.file_uploader("Archivo Excel (.xlsx)", type=["xlsx"])
    if uploaded is None:
        return

    try:
        records = _parse(uploaded)
    except Exception as exc:  # noqa: BLE001
        st.error(f"No se pudo leer el archivo: {exc}")
        return

    if not records:
        st.warning("El archivo no contiene filas de productos.")
        return

    deduped, skipped = _dedupe(records)

    c1, c2, c3 = st.columns(3)
    c1.metric("Filas en el archivo", len(records))
    c2.metric("Productos únicos", len(deduped))
    c3.metric("Duplicados a omitir", skipped)

    st.subheader("Vista previa")
    st.dataframe(
        _preview_rows(deduped), use_container_width=True, hide_index=True
    )

    if st.button("📥 Importar productos", type="primary"):
        result = db.import_products(
            deduped, sede=sede_destino, material_tipo=tipo_destino
        )
        db.log_audit(
            db.AUDIT_IMPORT,
            "Importar Productos",
            detalle=(
                f"Importados: {result['inserted']}, "
                f"Actualizados: {result['updated']}, "
                f"Duplicados omitidos: {skipped}, "
                f"Errores: {result['errors']}"
            ),
            usuario_rol=ctx["usuario_rol"],
            sede=sede_destino,
        )

        st.success("Importación finalizada.")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Importados", result["inserted"])
        m2.metric("Actualizados", result["updated"])
        m3.metric("Duplicados omitidos", skipped)
        m4.metric("Errores", result["errors"])

        if result["error_details"]:
            with st.expander("Detalle de errores"):
                for line in result["error_details"]:
                    st.write(f"• {line}")

        st.info(
            "Los productos ya aparecen en Productos, Inventario, Gestión de "
            "Inventario, Registro de Movimiento, Precios y Alertas."
        )
