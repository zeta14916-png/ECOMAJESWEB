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
- PRECIO DE VENTA SOLES -> prices.precio (+ precio_sugerido), COSTO INICIAL
  SOLES -> prices.costo, FAMILIA -> products.familia. These are stored but never
  surfaced in the worker Inventario screen or the Precios sheet UI.
"""

from __future__ import annotations

import time

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
            "precio_venta": _cell(r.get("precio_venta")),
            "costo": _cell(r.get("costo")),
            "familia": _cell(r.get("familia")),
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
            for f in ("unidad", "categoria", "precio_venta", "costo", "familia"):
                if not existing.get(f) and r.get(f):
                    existing[f] = r[f]
        else:
            by_code[code] = dict(r)
            order.append(code)

    deduped = [by_code[c] for c in order] + no_code
    return deduped, skipped


def _row_status(row: dict, snapshot: dict[str, dict]) -> str:
    """Label a row Nuevo / Actualizar / Sin cambios vs. the existing catalog."""
    code = (row.get("codigo") or "").strip()
    existing = snapshot.get(code) if code else None
    if existing is None:
        return "🟢 Nuevo"

    new_desc = (row.get("descripcion") or "").strip()
    new_unidad = (row.get("unidad") or "").strip() or "UNIDAD"
    new_familia = (row.get("familia") or "").strip()
    new_cat = db.resolve_categoria(row.get("categoria"), row.get("descripcion"))
    new_precio = db._import_decimal(row.get("precio_venta"))
    new_costo = db._import_decimal(row.get("costo"))

    old_desc = (existing.get("descripcion") or "").strip()
    changed = (
        db._fullest(old_desc, new_desc) != old_desc
        or new_cat != (existing.get("categoria") or "")
        or new_unidad != (existing.get("unidad") or "")
        or (new_familia and new_familia != (existing.get("familia") or ""))
        or (new_precio is not None and new_precio != existing.get("precio"))
        or (new_costo is not None and new_costo != existing.get("costo"))
    )
    return "🟡 Actualizar" if changed else "⚪ Sin cambios"


def _preview_rows(rows: list[dict], snapshot: dict[str, dict]) -> list[dict]:
    """Shape deduped rows for the on-screen preview (with defaults applied)."""
    out = []
    for r in rows:
        resolved = db.resolve_categoria(r.get("categoria"), r.get("descripcion"))
        out.append(
            {
                "Estado": _row_status(r, snapshot),
                "Código": r.get("codigo") or "—",
                "Descripción": r.get("descripcion") or "—",
                "Familia": r.get("familia") or "—",
                "Categoría": resolved,
                "Unidad": r.get("unidad") or "UNIDAD",
                "Precio de Venta": r.get("precio_venta") or "—",
                "Costo Inicial": r.get("costo") or "—",
                "Stock Inicial": 0,
            }
        )
    return out


@st.dialog("Confirmar importación")
def _confirm_dialog(
    deduped: list[dict],
    total_rows: int,
    skipped: int,
    sede: str,
    tipo: str,
    modo: str,
    usuario_rol: str,
) -> None:
    """Modal shown before writing: recap + Cancelar / Importar buttons."""
    st.markdown("**Estás a punto de importar:**")
    st.markdown(
        f"- **Filas totales:** {total_rows}\n"
        f"- **Productos únicos:** {len(deduped)}\n"
        f"- **Productos duplicados:** {skipped}\n"
        f"- **Destino:** {sede}\n"
        f"- **Tipo de material:** {db.TIPO_LABELS[tipo]}\n"
        f"- **Modo de importación:** {db.IMPORT_MODE_LABELS[modo]}"
    )

    b1, b2 = st.columns(2)
    if b1.button("❌ Cancelar", use_container_width=True):
        st.rerun()
    if b2.button(
        "✅ Importar Productos", type="primary", use_container_width=True
    ):
        start = time.perf_counter()
        result = db.import_products(
            deduped, sede=sede, material_tipo=tipo, mode=modo
        )
        elapsed = time.perf_counter() - start
        db.log_audit(
            db.AUDIT_IMPORT,
            "Importar Productos",
            detalle=(
                f"Modo: {modo}, Nuevos: {result['inserted']}, "
                f"Actualizados: {result['updated']}, "
                f"Omitidos por modo: {result['skipped_mode']}, "
                f"Duplicados omitidos: {skipped}, "
                f"Errores: {result['errors']}"
            ),
            usuario_rol=usuario_rol,
            sede=sede,
        )
        result["skipped_dup"] = skipped
        result["elapsed"] = elapsed
        st.session_state["import_result"] = result
        st.rerun()


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
            "(se guardan para precios/costos y reportes)\n\n"
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

    # --- Resumen de la última importación ---------------------------------- #
    if st.session_state.get("import_result"):
        _render_summary(st.session_state.pop("import_result"))
        st.divider()

    deduped, skipped = _dedupe(records)
    snapshot = db.get_products_import_snapshot(
        [r.get("codigo") for r in deduped]
    )

    # --- Modo de importación ---------------------------------------------- #
    modo = st.radio(
        "Modo de importación",
        db.IMPORT_MODES,
        format_func=lambda m: db.IMPORT_MODE_LABELS[m],
        help=(
            "Agregar solo nuevos: inserta únicamente productos que no existen. "
            "Actualizar existentes: solo modifica productos ya registrados. "
            "Sincronizar: inserta nuevos y actualiza existentes."
        ),
    )

    # --- Resumen + vista previa ------------------------------------------- #
    c1, c2, c3 = st.columns(3)
    c1.metric("Filas en el archivo", len(records))
    c2.metric("Productos únicos", len(deduped))
    c3.metric("Duplicados a omitir", skipped)

    st.markdown("**Vista previa**")
    st.dataframe(
        _preview_rows(deduped, snapshot),
        use_container_width=True,
        hide_index=True,
    )

    if st.button(
        "📥 Importar Productos", type="primary", use_container_width=True
    ):
        _confirm_dialog(
            deduped,
            len(records),
            skipped,
            sede_destino,
            tipo_destino,
            modo,
            ctx["usuario_rol"],
        )


def _render_summary(result: dict) -> None:
    """Render the post-import summary from a stored import result."""
    st.success("Importación completada")
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Productos nuevos", result["inserted"])
    m2.metric("Productos actualizados", result["updated"])
    m3.metric("Omitidos por modo", result.get("skipped_mode", 0))
    m4.metric("Duplicados omitidos", result.get("skipped_dup", 0))
    m5.metric("Errores encontrados", result["errors"])
    m6.metric("Tiempo de importación", f"{result.get('elapsed', 0):.1f} s")

    if result.get("error_details"):
        with st.expander("Detalle de errores"):
            for line in result["error_details"]:
                st.write(f"• {line}")

    st.info(
        "Los productos ya aparecen en Productos, Inventario, Gestión de "
        "Inventario, Registro de Movimiento, Precios y Alertas."
    )
