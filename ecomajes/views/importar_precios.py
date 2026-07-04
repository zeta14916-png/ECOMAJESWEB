"""Price importer (GERENCIA) — update pricing fields only, match by codigo.

Upload a **multi-sheet** Excel (each sheet is a product family such as PLATINA,
ANGULO, TUBO REDONDO, CUADRADO, RECTANGULAR, PLANCHA, SCH 40 Y 80, BARRA
REDONDA, ELECTRODO, BISAGRAS, DE TODO, POLEAS). Every sheet is read and merged.

Rules:
- Never creates products. Rows are matched to existing products by Código.
- Only pricing fields are written; códigos with no match are shown before
  importing (nothing is written for them).
- Recognised price columns: Precio, Costo, Peso, P1, P2, P3, Venta mínimo,
  Venta oficial, Venta por 3 m, Venta por metro.
"""

from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from ecomajes import db
from ecomajes.views import _import_common

cell = _import_common.cell

# Spreadsheet header -> canonical price field. Keys are lower-cased + stripped.
_COLUMN_ALIASES = {
    "codigo": "codigo",
    "código": "codigo",
    "cod": "codigo",
    "cod.": "codigo",
    "precio": "precio",
    "precio venta": "precio",
    "precio de venta": "precio",
    "precio de venta soles": "precio",
    "costo": "costo",
    "costo inicial": "costo",
    "costo inicial soles": "costo",
    "peso": "peso",
    "p1": "p1",
    "p2": "p2",
    "p3": "p3",
    "venta minimo": "precio_minimo",
    "venta mínimo": "precio_minimo",
    "venta minima": "precio_minimo",
    "venta mínima": "precio_minimo",
    "precio minimo": "precio_minimo",
    "precio mínimo": "precio_minimo",
    "venta oficial": "venta_oficial",
    "venta por 3 m": "venta_3m",
    "venta por 3m": "venta_3m",
    "venta 3 m": "venta_3m",
    "venta 3m": "venta_3m",
    "venta por metro": "venta_metro",
    "venta metro": "venta_metro",
    "venta x metro": "venta_metro",
}

_FIELDS = db.PRICE_IMPORT_FIELDS  # canonical numeric fields


def _parse(file) -> list[dict]:
    """Read every sheet of the workbook into canonical price row dicts."""
    sheets = pd.read_excel(file, sheet_name=None)
    records: list[dict] = []
    for _name, df in sheets.items():
        rename = {}
        for col in df.columns:
            canon = _COLUMN_ALIASES.get(str(col).strip().lower())
            if canon:
                rename[col] = canon
        df = df.rename(columns=rename)
        if "codigo" not in df.columns:
            continue  # sheet without a Código column can't be matched
        for _, r in df.iterrows():
            row = {"codigo": cell(r.get("codigo"))}
            for f in _FIELDS:
                row[f] = cell(r.get(f)) if f in df.columns else ""
            if row["codigo"]:
                records.append(row)
    return records


def _dedupe(records: list[dict]) -> tuple[list[dict], int]:
    """Collapse repeated códigos across sheets, keeping first non-empty values.

    Returns (deduped_rows, skipped_duplicates).
    """
    by_code: dict[str, dict] = {}
    order: list[str] = []
    skipped = 0
    for r in records:
        code = r["codigo"]
        if code in by_code:
            skipped += 1
            existing = by_code[code]
            for f in _FIELDS:
                if not existing.get(f) and r.get(f):
                    existing[f] = r[f]
        else:
            by_code[code] = dict(r)
            order.append(code)
    return [by_code[c] for c in order], skipped


_PREVIEW_LABELS = {
    "precio": "Precio",
    "costo": "Costo",
    "peso": "Peso",
    "p1": "P1",
    "p2": "P2",
    "p3": "P3",
    "precio_minimo": "Venta mínimo",
    "venta_oficial": "Venta oficial",
    "venta_3m": "Venta por 3 m",
    "venta_metro": "Venta por metro",
}


def _preview_rows(rows: list[dict], snapshot: dict[str, dict]) -> list[dict]:
    """Shape deduped rows for the on-screen preview."""
    out = []
    for r in rows:
        code = r["codigo"]
        existing = snapshot.get(code)
        row = {
            "Estado": "🟢 Encontrado" if existing else "🔴 No encontrado",
            "Código": code,
            "Descripción": (existing or {}).get("descripcion") or "—",
        }
        for f in _FIELDS:
            row[_PREVIEW_LABELS[f]] = r.get(f) or "—"
        out.append(row)
    return out


@st.dialog("Confirmar importación de precios")
def _confirm_dialog(
    to_import: list[dict],
    total_rows: int,
    unique: int,
    skipped: int,
    not_found: int,
    usuario_rol: str,
) -> None:
    """Modal shown before writing: recap + Cancelar / Importar buttons."""
    st.markdown("**Estás a punto de actualizar precios:**")
    st.markdown(
        f"- **Filas totales:** {total_rows}\n"
        f"- **Códigos únicos:** {unique}\n"
        f"- **Duplicados omitidos:** {skipped}\n"
        f"- **No encontrados (se omiten):** {not_found}\n"
        f"- **A actualizar:** {len(to_import)}"
    )
    if not to_import:
        st.info("No hay productos existentes que actualizar.")

    b1, b2 = st.columns(2)
    if b1.button("❌ Cancelar", use_container_width=True):
        st.rerun()
    if b2.button(
        "✅ Importar Precios",
        type="primary",
        use_container_width=True,
        disabled=not to_import,
    ):
        backup = db.create_products_backup("precios")
        outcome: dict
        try:
            start = time.perf_counter()
            result = db.import_prices(to_import)
            elapsed = time.perf_counter() - start
        except Exception as exc:  # noqa: BLE001
            restored = True
            try:
                db.restore_products_backup(backup["id"])
            except Exception:  # noqa: BLE001
                restored = False
            outcome = {
                "failed": True,
                "error": str(exc),
                "restored": restored,
                "backup": backup,
            }
        else:
            db.log_audit(
                db.AUDIT_IMPORT,
                "Importar Precios",
                detalle=(
                    f"Actualizados: {result['updated']}, "
                    f"No encontrados: {len(result['not_found'])}, "
                    f"Duplicados omitidos: {skipped}, "
                    f"Errores: {result['errors']}"
                ),
                usuario_rol=usuario_rol,
            )
            result["skipped_dup"] = skipped
            result["elapsed"] = elapsed
            result["backup"] = backup
            outcome = result
        st.session_state["price_import_result"] = outcome
        st.rerun()


def _render_summary(result: dict) -> None:
    """Render the post-import summary from a stored import result."""
    if result.get("backup"):
        st.success("Respaldo creado correctamente.")

    if result.get("failed"):
        if result.get("restored"):
            st.error(
                "La importación falló. Se restauró automáticamente el "
                "inventario anterior."
            )
        else:
            st.error(
                "La importación falló y no se pudo restaurar el respaldo "
                "automáticamente. Usa «Restaurar último respaldo»."
            )
        st.caption(f"Detalle: {result.get('error', 'error desconocido')}")
        return

    st.success("Importación de precios completada")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Precios actualizados", result["updated"])
    m2.metric("No encontrados", len(result.get("not_found", [])))
    m3.metric("Errores encontrados", result["errors"])
    m4.metric("Tiempo de importación", f"{result.get('elapsed', 0):.1f} s")

    if result.get("not_found"):
        with st.expander(
            f"Códigos no encontrados ({len(result['not_found'])})"
        ):
            st.write(", ".join(result["not_found"]))
    if result.get("error_details"):
        with st.expander("Detalle de errores"):
            for line in result["error_details"]:
                st.write(f"• {line}")


def render(ctx: dict) -> None:
    st.header(ctx["title"])
    st.caption(ctx["breadcrumb"])

    _import_common.render_backup_panel(ctx, "Importar Precios")

    st.markdown(
        "Sube un archivo **Excel** con tus precios. Se leen **todas las hojas** "
        "(PLATINA, ANGULO, TUBO REDONDO, etc.) y se actualizan únicamente los "
        "precios de productos que ya existen, buscándolos por **Código**."
    )
    with st.expander("¿Qué columnas puede tener el Excel?"):
        st.markdown(
            "- **CÓDIGO** (obligatorio, es la llave para encontrar el producto)\n"
            "- Precio, Costo, Peso, P1, P2, P3\n"
            "- Venta mínimo, Venta oficial, Venta por 3 m, Venta por metro\n\n"
            "No se crean productos nuevos: los códigos que no existan se listan "
            "antes de importar y se omiten."
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
        st.warning(
            "El archivo no contiene filas con Código y precios reconocibles."
        )
        return

    if st.session_state.get("price_import_result"):
        _render_summary(st.session_state.pop("price_import_result"))
        st.divider()

    deduped, skipped = _dedupe(records)
    snapshot = db.get_products_import_snapshot([r["codigo"] for r in deduped])

    to_import = [r for r in deduped if r["codigo"] in snapshot]
    not_found = [r["codigo"] for r in deduped if r["codigo"] not in snapshot]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Filas en el archivo", len(records))
    c2.metric("Códigos únicos", len(deduped))
    c3.metric("Duplicados a omitir", skipped)
    c4.metric("No encontrados", len(not_found))

    if not_found:
        with st.expander(
            f"⚠️ Productos no encontrados por Código ({len(not_found)}) — "
            "se omitirán"
        ):
            st.write(", ".join(not_found))

    st.markdown("**Vista previa**")
    st.dataframe(
        _preview_rows(deduped, snapshot),
        use_container_width=True,
        hide_index=True,
    )

    if st.button(
        "📥 Importar Precios", type="primary", use_container_width=True
    ):
        _confirm_dialog(
            to_import,
            len(records),
            len(deduped),
            skipped,
            len(not_found),
            ctx["usuario_rol"],
        )
