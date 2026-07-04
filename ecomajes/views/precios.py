"""Price list view for ECOMAJES ERP.

The single place where prices are maintained. Shows a spreadsheet-like editor
(``st.data_editor``) with one row per product in the current scope. Prices can
be edited inline and saved; rows without a stored price are seeded from the
product data (code / description / unit).

Only GERENCIA may edit prices. Any other role that reaches this view sees it in
read-only mode. Saved prices are used automatically for future sales (see
``db.register_movement``) and movement reports.
"""

from decimal import Decimal, InvalidOperation

import pandas as pd
import streamlit as st

from ecomajes import config, db

# Display column -> internal price field.
_TEXT_COLS = {
    "Código": "codigo",
    "Descripción": "descripcion",
    "Categoría": "categoria",
    "Unidad": "unidad",
    "Observaciones": "observaciones",
}
_NUM_COLS = {
    "Peso": "peso",
    "Precio en dólares": "precio",
    "Costo": "costo",
    "P1": "p1",
    "P2": "p2",
    "P3": "p3",
    "Venta mínima": "precio_minimo",
    "Venta oficial": "venta_oficial",
    "Venta por 3 metros": "venta_3m",
    "Venta por metro": "venta_metro",
}
# Column order shown in the sheet.
_ORDER = [
    "Código",
    "Descripción",
    "Categoría",
    "Unidad",
    "Peso",
    "Precio en dólares",
    "Costo",
    "P1",
    "P2",
    "P3",
    "Venta mínima",
    "Venta oficial",
    "Venta por 3 metros",
    "Venta por metro",
    "Observaciones",
]


def _to_display_rows(rows: list[dict]) -> tuple[list[dict], list[int]]:
    """Build display dicts (seeding defaults) and the parallel product_id list."""
    display: list[dict] = []
    product_ids: list[int] = []
    for r in rows:
        product_ids.append(r["product_id"])
        display.append(
            {
                "Código": r.get("codigo") or (r.get("sku") or ""),
                "Descripción": r.get("descripcion") or r.get("nombre") or "",
                "Categoría": r.get("categoria") or "",
                "Unidad": r.get("unidad") or r.get("producto_unidad") or "",
                "Peso": _as_float(r.get("peso")),
                "Precio en dólares": _as_float(r.get("precio")),
                "Costo": _as_float(r.get("costo")),
                "P1": _as_float(r.get("p1")),
                "P2": _as_float(r.get("p2")),
                "P3": _as_float(r.get("p3")),
                "Venta mínima": _as_float(r.get("precio_minimo")),
                "Venta oficial": _as_float(r.get("venta_oficial")),
                "Venta por 3 metros": _as_float(r.get("venta_3m")),
                "Venta por metro": _as_float(r.get("venta_metro")),
                "Observaciones": r.get("observaciones") or "",
            }
        )
    return display, product_ids


def _as_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_decimal(value) -> Decimal | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _parse_text(value) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


def _column_config() -> dict:
    config_map = {}
    for col in _TEXT_COLS:
        config_map[col] = st.column_config.TextColumn(col)
    for col in _NUM_COLS:
        fmt = "%.3f" if col == "Peso" else "%.2f"
        config_map[col] = st.column_config.NumberColumn(
            col, format=fmt, min_value=0.0
        )
    return config_map


def _save(edited: pd.DataFrame, product_ids: list[int]) -> int:
    rows: list[dict] = []
    for pos, product_id in enumerate(product_ids):
        record = edited.iloc[pos]
        row: dict = {"product_id": product_id}
        for col, field in _TEXT_COLS.items():
            row[field] = _parse_text(record[col])
        for col, field in _NUM_COLS.items():
            row[field] = _parse_decimal(record[col])
        # Keep the suggested sale price (used by ventas) in sync with the
        # maintained price; there is no separate "precio sugerido" column.
        row["precio_sugerido"] = row.get("precio")
        rows.append(row)
    return db.save_prices(rows)


def render(ctx: dict) -> None:
    st.header(ctx["title"])
    st.caption(ctx["breadcrumb"])

    can_edit = ctx["usuario_rol"] == config.ROLE_GERENCIA
    if can_edit:
        st.write(
            "Edita los precios como en una hoja de cálculo y guarda los cambios. "
            "Los precios se aplican automáticamente a las ventas futuras."
        )
    else:
        st.info("Solo lectura. Los precios los administra únicamente GERENCIA.")

    rows = db.list_prices(
        sede=ctx["sede"],
        material_tipo=ctx["material_tipo"],
        include_all_sedes=ctx["include_all_sedes"],
    )
    if not rows:
        st.info(
            "No hay productos en este ámbito todavía. "
            "Registra productos en Inventario para poder asignarles precios."
        )
        return

    display, product_ids = _to_display_rows(rows)
    df = pd.DataFrame(display, columns=_ORDER)

    edited = st.data_editor(
        df,
        num_rows="fixed",
        use_container_width=True,
        hide_index=True,
        column_config=_column_config(),
        disabled=not can_edit,
        key="precios_editor",
    )

    if not can_edit:
        return

    if st.button("💾 Guardar precios", type="primary"):
        try:
            n = _save(edited, product_ids)
        except Exception as exc:  # noqa: BLE001
            st.error(f"No se pudieron guardar los precios: {exc}")
        else:
            db.log_audit(
                db.AUDIT_PRICE_CHANGED,
                "Precios",
                detalle=f"{n} producto(s) actualizado(s)",
                usuario_rol=ctx["usuario_rol"],
                sede=ctx["sede"],
            )
            st.success(f"Precios guardados para {n} producto(s).")
            st.rerun()
