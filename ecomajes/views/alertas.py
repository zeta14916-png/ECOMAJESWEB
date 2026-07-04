"""Alertas view for ÁREA ADMINISTRATIVA.

Read-only replenishment alerts scoped to the current sede and material type.
Shows products that are agotados (stock <= 0) or con stock bajo (stock at or
below its stock mínimo), with a suggested quantity to order. Reuses the existing
catalog data only — no inventory or movement logic is changed here.
"""

from decimal import Decimal

import streamlit as st

from ecomajes import db


def _num(value) -> Decimal:
    return Decimal(value) if value is not None else Decimal("0")


def _fmt(value: Decimal) -> float:
    return float(value)


def _alert_rows(ctx: dict) -> list[dict]:
    """Return catalog products for this sede/material that need replenishment."""
    products = db.list_catalog_products(
        sede=ctx["sede"],
        include_all_sedes=ctx["include_all_sedes"],
    )
    material_tipo = ctx.get("material_tipo")

    rows: list[dict] = []
    for p in products:
        if not p["activo"]:
            continue
        if material_tipo is not None and p["material_tipo"] != material_tipo:
            continue

        stock = _num(p["stock"])
        minimo = _num(p["stock_minimo"])

        agotado = stock <= 0
        bajo = (not agotado) and minimo > 0 and stock <= minimo
        if not (agotado or bajo):
            continue

        sugerida = minimo - stock
        if sugerida < 0:
            sugerida = Decimal("0")

        rows.append(
            {
                "Código": p["codigo"] or "—",
                "Descripción": p["descripcion"] or p["nombre"],
                "Categoría": p["categoria"] or "—",
                "Stock actual": _fmt(stock),
                "Stock mínimo": _fmt(minimo),
                "Cantidad sugerida a pedir": _fmt(sugerida),
                "Estado": "Agotado" if agotado else "Stock bajo",
            }
        )

    # Agotados first, then lowest stock first.
    rows.sort(key=lambda r: (r["Estado"] != "Agotado", r["Stock actual"]))
    return rows


def render(ctx: dict) -> None:
    st.header(ctx["title"])
    st.caption(ctx["breadcrumb"])
    st.caption(f"Alertas de inventario para **{ctx['sede']}** (solo esta sede).")

    rows = _alert_rows(ctx)

    agotados = [r for r in rows if r["Estado"] == "Agotado"]
    bajos = [r for r in rows if r["Estado"] == "Stock bajo"]

    c1, c2, c3 = st.columns(3)
    c1.metric("Agotados", len(agotados))
    c2.metric("Stock bajo", len(bajos))
    c3.metric("Productos a reponer", len(rows))

    st.divider()
    st.subheader("Productos que necesitan reposición")
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.success("No hay productos con stock bajo ni agotados en esta sede.")
