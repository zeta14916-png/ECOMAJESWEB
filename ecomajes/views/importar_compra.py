"""Purchase (compra) import view for ECOMAJES ERP.

Allows importing a batch purchase of existing products via Excel spreadsheet.
Each valid row increases the product stock (entrada movement) and records the
supplier, quantity, unit cost and date for auditing purposes.

Rules:
- Products must already exist in the system (matched by Código + sede).
- Stock is increased automatically via register_movement (tipo='entrada').
- Prices are NEVER modified.
- All changes are recorded in the audit log.
- Only the chosen sede is affected.
"""

from __future__ import annotations

import io
import time
from decimal import Decimal, InvalidOperation

import pandas as pd
import streamlit as st

from ecomajes import config, db
from ecomajes.views import _import_common

cell = _import_common.cell

# ── Column name aliases (lower-cased) → canonical field name ─────────────── #
_COLUMN_ALIASES: dict[str, str] = {
    "proveedor": "proveedor",
    "supplier": "proveedor",
    "empresa": "proveedor",
    "codigo": "codigo",
    "código": "codigo",
    "cod": "codigo",
    "cod.": "codigo",
    "descripcion": "descripcion",
    "descripción": "descripcion",
    "producto": "descripcion",
    "nombre": "descripcion",
    "cantidad": "cantidad",
    "qty": "cantidad",
    "cantidad comprada": "cantidad",
    "unidades": "cantidad",
    "costo unitario": "costo",
    "costo": "costo",
    "precio costo": "costo",
    "precio compra": "costo",
    "costo unit": "costo",
    "fecha": "fecha",
    "date": "fecha",
    "fecha compra": "fecha",
}


# ── Excel template ─────────────────────────────────────────────────────────── #
def _template_bytes() -> bytes:
    """Build and return an empty Excel template for purchase imports."""
    df = pd.DataFrame(
        columns=["Proveedor", "Código", "Descripción", "Cantidad", "Costo unitario", "Fecha"]
    )
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


# ── Parsing ────────────────────────────────────────────────────────────────── #
def _parse(file) -> list[dict]:
    """Read all sheets from the workbook; return normalised row dicts."""
    sheets = pd.read_excel(file, sheet_name=None)
    records: list[dict] = []
    for _sheet, df in sheets.items():
        rename: dict[str, str] = {}
        for col in df.columns:
            canon = _COLUMN_ALIASES.get(str(col).strip().lower())
            if canon:
                rename[col] = canon
        df = df.rename(columns=rename)
        if "codigo" not in df.columns:
            continue
        for _, r in df.iterrows():
            row = {
                "proveedor": cell(r.get("proveedor", "")),
                "codigo": cell(r.get("codigo")),
                "descripcion": cell(r.get("descripcion", "")),
                "cantidad": cell(r.get("cantidad", "")),
                "costo": cell(r.get("costo", "")),
                "fecha": cell(r.get("fecha", "")),
            }
            if row["codigo"] and row["cantidad"]:
                records.append(row)
    return records


# ── Validation ─────────────────────────────────────────────────────────────── #
def _validate_row(r: dict, snapshot: dict[str, dict]) -> tuple[bool, str]:
    """Return (is_valid, error_message) for a single row."""
    if not r.get("codigo"):
        return False, "Código vacío"
    if r["codigo"] not in snapshot:
        return False, "No encontrado en sede"
    try:
        qty = Decimal(str(r["cantidad"]).replace(",", "."))
        if qty <= 0:
            return False, "Cantidad debe ser mayor que cero"
    except (InvalidOperation, ValueError):
        return False, f"Cantidad inválida: {r['cantidad']}"
    if r.get("costo"):
        try:
            costo_str = str(r["costo"]).replace("S/", "").replace(",", ".").strip()
            cst = Decimal(costo_str)
            if cst < 0:
                return False, "Costo no puede ser negativo"
        except (InvalidOperation, ValueError):
            return False, f"Costo inválido: {r['costo']}"
    return True, ""


def _parse_decimal(value: str) -> Decimal | None:
    """Parse a decimal string, tolerating S/ and comma separators."""
    if not value:
        return None
    try:
        return Decimal(str(value).replace("S/", "").replace(",", ".").strip())
    except (InvalidOperation, ValueError):
        return None


# ── Preview ────────────────────────────────────────────────────────────────── #
def _preview_rows(records: list[dict], snapshot: dict[str, dict]) -> list[dict]:
    out = []
    for r in records:
        valid, err = _validate_row(r, snapshot)
        existing = snapshot.get(r["codigo"], {})
        qty = _parse_decimal(r.get("cantidad", ""))
        stock_actual = existing.get("stock") if existing else None
        out.append(
            {
                "Estado": "🟢 Válido" if valid else f"🔴 {err}",
                "Proveedor": r.get("proveedor") or "—",
                "Código": r["codigo"],
                "Descripción": (
                    existing.get("descripcion") or r.get("descripcion") or "—"
                ),
                "Stock actual": (
                    f"{float(stock_actual):g}" if stock_actual is not None else "—"
                ),
                "Cantidad a agregar": float(qty) if qty is not None else r.get("cantidad"),
                "Stock nuevo": (
                    f"{float(stock_actual) + float(qty):g}"
                    if stock_actual is not None and qty is not None
                    else "—"
                ),
                "Costo unitario": r.get("costo") or "—",
                "Fecha compra": r.get("fecha") or "—",
            }
        )
    return out


# ── Import dialog ──────────────────────────────────────────────────────────── #
@st.dialog("Confirmar importación de compra")
def _confirm_dialog(
    valid_rows: list[dict],
    total_rows: int,
    not_found_count: int,
    invalid_count: int,
    sede: str,
    usuario_rol: str,
) -> None:
    """Confirmation modal before writing movements to the DB."""
    st.markdown("**Estás a punto de registrar la compra de productos:**")
    st.markdown(
        f"- **Filas totales:** {total_rows}\n"
        f"- **A importar (válidos):** {len(valid_rows)}\n"
        f"- **No encontrados (se omiten):** {not_found_count}\n"
        f"- **Inválidos (se omiten):** {invalid_count}\n"
        f"- **Sede destino:** {sede}"
    )
    if not valid_rows:
        st.info("No hay productos válidos para importar en esta sede.")

    b1, b2 = st.columns(2)
    if b1.button("❌ Cancelar", use_container_width=True):
        st.rerun()

    if b2.button(
        "✅ Importar Compra",
        type="primary",
        use_container_width=True,
        disabled=not valid_rows,
    ):
        errors: list[str] = []
        imported = 0
        start = time.perf_counter()

        # Re-fetch snapshot to avoid stale data.
        all_codes = [r["codigo"] for r in valid_rows]
        snapshot = db.get_stock_import_snapshot(all_codes, sede)

        for r in valid_rows:
            info = snapshot.get(r["codigo"])
            if not info:
                errors.append(f"{r['codigo']}: no encontrado al confirmar")
                continue
            try:
                qty = Decimal(str(r["cantidad"]).replace(",", "."))
                costo_unit = _parse_decimal(r.get("costo", ""))

                # Build descriptive nota for audit trail.
                nota_parts = ["Importación de compra"]
                if r.get("proveedor"):
                    nota_parts.append(f"Proveedor: {r['proveedor']}")
                if r.get("fecha"):
                    nota_parts.append(f"Fecha: {r['fecha']}")
                if costo_unit is not None:
                    nota_parts.append(f"Costo unit.: S/ {float(costo_unit):,.2f}")
                nota = " | ".join(nota_parts)

                db.register_movement(
                    product_id=info["id"],
                    tipo=db.MOVEMENT_ENTRADA,
                    cantidad=qty,
                    nota=nota,
                    usuario_rol=usuario_rol,
                    sede=sede,
                )
                imported += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{r['codigo']}: {exc}")

        elapsed = time.perf_counter() - start

        db.log_audit(
            db.AUDIT_IMPORT,
            "Importar Compra",
            detalle=(
                f"Sede: {sede}, Importados: {imported}, "
                f"Errores: {len(errors)}, Tiempo: {elapsed:.1f}s"
            ),
            usuario_rol=usuario_rol,
            sede=sede,
        )

        st.session_state["compra_import_result"] = {
            "imported": imported,
            "errors": errors,
            "elapsed": elapsed,
            "sede": sede,
        }
        st.rerun()


# ── Result summary ─────────────────────────────────────────────────────────── #
def _render_summary(result: dict) -> None:
    if result.get("imported", 0) == 0 and result.get("errors"):
        st.error("La importación no pudo completarse.")
    else:
        st.success(
            f"✅ Importación de compra completada · {result.get('sede', '')} · "
            f"**{result.get('imported', 0)} productos** registrados "
            f"en {result.get('elapsed', 0):.1f} s."
        )
    if result.get("errors"):
        with st.expander(f"⚠️ Errores ({len(result['errors'])})"):
            for e in result["errors"]:
                st.write(f"• {e}")


# ── Main render ────────────────────────────────────────────────────────────── #
def render(ctx: dict) -> None:
    st.header(ctx["title"])
    st.caption(ctx["breadcrumb"])

    st.markdown(
        "Sube un **Excel** con los productos comprados. "
        "El stock se aumenta automáticamente y cada producto genera un "
        "**movimiento de entrada** para auditoría. "
        "**Los precios no se modifican.**"
    )

    # ── Download template ────────────────────────────────────────────────── #
    with st.expander("📄 Descargar plantilla Excel"):
        st.caption(
            "Completa las columnas: **Proveedor**, **Código**, **Descripción** "
            "(referencial), **Cantidad**, **Costo unitario**, **Fecha**. "
            "Solo Código y Cantidad son obligatorios."
        )
        st.download_button(
            label="⬇️ Descargar plantilla",
            data=_template_bytes(),
            file_name="plantilla_importar_compra.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet"
            ),
        )

    # ── Sede selection ───────────────────────────────────────────────────── #
    default_sede = (
        ctx["sede"]
        if ctx["sede"] in (config.SEDE_PRINCIPAL, config.SEDE_SUCURSAL)
        else config.SEDE_PRINCIPAL
    )
    sede_options = [config.SEDE_PRINCIPAL, config.SEDE_SUCURSAL]
    sede_destino = st.selectbox(
        "Sede de la compra",
        sede_options,
        index=sede_options.index(default_sede),
        help="Los productos se buscarán en esta sede y el stock se actualizará allí.",
    )

    # ── File upload ──────────────────────────────────────────────────────── #
    uploaded = st.file_uploader(
        "Archivo Excel (.xlsx)",
        type=["xlsx"],
        help="Sube el archivo con los productos de la compra.",
    )
    if uploaded is None:
        return

    try:
        records = _parse(uploaded)
    except Exception as exc:  # noqa: BLE001
        st.error(f"No se pudo leer el archivo: {exc}")
        return

    if not records:
        st.warning(
            "El archivo no contiene filas con Código y Cantidad reconocibles."
        )
        return

    # ── Show previous import result if any ───────────────────────────────── #
    if st.session_state.get("compra_import_result"):
        _render_summary(st.session_state.pop("compra_import_result"))
        st.divider()

    # ── Validate against DB ──────────────────────────────────────────────── #
    all_codes = [r["codigo"] for r in records if r.get("codigo")]
    snapshot = db.get_stock_import_snapshot(all_codes, sede_destino)

    valid_rows: list[dict] = []
    not_found_count = 0
    invalid_count = 0
    for r in records:
        ok, err = _validate_row(r, snapshot)
        if ok:
            valid_rows.append(r)
        elif "no encontrado" in err.lower():
            not_found_count += 1
        else:
            invalid_count += 1

    # ── Metrics ──────────────────────────────────────────────────────────── #
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Filas en archivo", len(records))
    c2.metric("Válidos a importar", len(valid_rows))
    c3.metric("No encontrados", not_found_count)
    c4.metric("Inválidos", invalid_count)

    if not_found_count or invalid_count:
        st.warning(
            f"Los {not_found_count + invalid_count} registros con problemas "
            "aparecen como 🔴 en la vista previa y serán omitidos."
        )

    # ── Preview ──────────────────────────────────────────────────────────── #
    st.markdown("**Vista previa**")
    st.dataframe(
        _preview_rows(records, snapshot),
        use_container_width=True,
        hide_index=True,
    )

    # ── Import button ─────────────────────────────────────────────────────── #
    if st.button(
        "📥 Importar Compra de Productos",
        type="primary",
        use_container_width=True,
        disabled=not valid_rows,
    ):
        _confirm_dialog(
            valid_rows,
            len(records),
            not_found_count,
            invalid_count,
            sede_destino,
            ctx["usuario_rol"],
        )
