"""Stock importer (GERENCIA) — update stock quantities only, per sede.

Upload an Excel with Código, Stock and (optionally) Stock mínimo, choose the
sede (Principal / Sucursal), preview, then import.

Rules:
- Never creates products and never touches prices or descriptions.
- Matches existing products by Código within the chosen sede; códigos that don't
  exist there are shown before importing and are skipped.
- Only stock (and stock_minimo when present) is updated.
"""

from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from ecomajes import config, db
from ecomajes.views import _import_common

cell = _import_common.cell

# Spreadsheet header -> canonical field. Keys are lower-cased + stripped.
_COLUMN_ALIASES = {
    "codigo": "codigo",
    "código": "codigo",
    "cod": "codigo",
    "cod.": "codigo",
    "stock": "stock",
    "existencia": "stock",
    "existencias": "stock",
    "cantidad": "stock",
    "stock actual": "stock",
    "stock minimo": "stock_minimo",
    "stock mínimo": "stock_minimo",
    "minimo": "stock_minimo",
    "mínimo": "stock_minimo",
    "stock min": "stock_minimo",
}


def _parse(file) -> list[dict]:
    """Read every sheet of the workbook into canonical stock row dicts."""
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
            continue
        for _, r in df.iterrows():
            row = {
                "codigo": cell(r.get("codigo")),
                "stock": cell(r.get("stock")) if "stock" in df.columns else "",
                "stock_minimo": (
                    cell(r.get("stock_minimo"))
                    if "stock_minimo" in df.columns
                    else ""
                ),
            }
            if row["codigo"] and (row["stock"] or row["stock_minimo"]):
                records.append(row)
    return records


def _dedupe(records: list[dict]) -> tuple[list[dict], int]:
    """Collapse repeated códigos, keeping the last non-empty value.

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
            for f in ("stock", "stock_minimo"):
                if r.get(f):
                    existing[f] = r[f]
        else:
            by_code[code] = dict(r)
            order.append(code)
    return [by_code[c] for c in order], skipped


def _preview_rows(rows: list[dict], snapshot: dict[str, dict]) -> list[dict]:
    """Shape deduped rows for the on-screen preview."""
    out = []
    for r in rows:
        code = r["codigo"]
        existing = snapshot.get(code)
        out.append(
            {
                "Estado": "🟢 Encontrado" if existing else "🔴 No encontrado",
                "Código": code,
                "Descripción": (existing or {}).get("descripcion") or "—",
                "Stock actual": (
                    "—" if existing is None else f"{existing['stock']:g}"
                ),
                "Stock nuevo": r.get("stock") or "—",
                "Stock mínimo": r.get("stock_minimo") or "—",
            }
        )
    return out


@st.dialog("Confirmar importación de stock")
def _confirm_dialog(
    to_import: list[dict],
    total_rows: int,
    unique: int,
    skipped: int,
    not_found: int,
    sede: str,
    usuario_rol: str,
) -> None:
    """Modal shown before writing: recap + Cancelar / Importar buttons."""
    st.markdown("**Estás a punto de actualizar el stock:**")
    st.markdown(
        f"- **Filas totales:** {total_rows}\n"
        f"- **Códigos únicos:** {unique}\n"
        f"- **Duplicados omitidos:** {skipped}\n"
        f"- **No encontrados en {sede} (se omiten):** {not_found}\n"
        f"- **Sede destino:** {sede}\n"
        f"- **A actualizar:** {len(to_import)}"
    )
    if not to_import:
        st.info("No hay productos en esta sede que actualizar.")

    b1, b2 = st.columns(2)
    if b1.button("❌ Cancelar", use_container_width=True):
        st.rerun()
    if b2.button(
        "✅ Importar Stock",
        type="primary",
        use_container_width=True,
        disabled=not to_import,
    ):
        backup = db.create_products_backup("stock")
        outcome: dict
        try:
            start = time.perf_counter()
            result = db.import_stock(to_import, sede)
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
                "Importar Stock",
                detalle=(
                    f"Sede: {sede}, Actualizados: {result['updated']}, "
                    f"No encontrados: {len(result['not_found'])}, "
                    f"Duplicados omitidos: {skipped}, "
                    f"Errores: {result['errors']}"
                ),
                usuario_rol=usuario_rol,
                sede=sede,
            )
            result["skipped_dup"] = skipped
            result["elapsed"] = elapsed
            result["backup"] = backup
            result["sede"] = sede
            outcome = result
        st.session_state["stock_import_result"] = outcome
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

    st.success(f"Importación de stock completada · {result.get('sede', '')}")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Stock actualizado", result["updated"])
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

    _import_common.render_backup_panel(ctx, "Importar Stock")

    st.markdown(
        "Sube un archivo **Excel** con **Código** y **Stock** (y opcionalmente "
        "**Stock mínimo**). Solo se actualiza la cantidad de stock de productos "
        "que ya existen en la sede elegida. No se crean productos ni se tocan "
        "precios o descripciones."
    )

    default_sede = (
        ctx["sede"]
        if ctx["sede"] in (config.SEDE_PRINCIPAL, config.SEDE_SUCURSAL)
        else config.SEDE_PRINCIPAL
    )
    sede_options = [config.SEDE_PRINCIPAL, config.SEDE_SUCURSAL]
    sede_destino = st.selectbox(
        "Sede a actualizar",
        sede_options,
        index=sede_options.index(default_sede),
        help="El stock se actualiza solo para productos de esta sede.",
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
            "El archivo no contiene filas con Código y Stock reconocibles."
        )
        return

    if st.session_state.get("stock_import_result"):
        _render_summary(st.session_state.pop("stock_import_result"))
        st.divider()

    deduped, skipped = _dedupe(records)
    snapshot = db.get_stock_import_snapshot(
        [r["codigo"] for r in deduped], sede_destino
    )

    to_import = [r for r in deduped if r["codigo"] in snapshot]
    not_found = [r["codigo"] for r in deduped if r["codigo"] not in snapshot]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Filas en el archivo", len(records))
    c2.metric("Códigos únicos", len(deduped))
    c3.metric("Duplicados a omitir", skipped)
    c4.metric("No encontrados", len(not_found))

    if not_found:
        with st.expander(
            f"⚠️ Códigos no encontrados en {sede_destino} "
            f"({len(not_found)}) — se omitirán"
        ):
            st.write(", ".join(not_found))

    st.markdown("**Vista previa**")
    st.dataframe(
        _preview_rows(deduped, snapshot),
        use_container_width=True,
        hide_index=True,
    )

    if st.button(
        "📥 Importar Stock", type="primary", use_container_width=True
    ):
        _confirm_dialog(
            to_import,
            len(records),
            len(deduped),
            skipped,
            len(not_found),
            sede_destino,
            ctx["usuario_rol"],
        )
