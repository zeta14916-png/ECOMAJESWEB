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
                "id": p["id"],
                "codigo": p["codigo"],
                "descripcion": p["descripcion"] or p["nombre"],
                "categoria": p["categoria"] or "—",
                "material_tipo": p["material_tipo"],
                "stock": stock,
                "minimo": minimo,
                "sugerida": sugerida,
                "estado": "Agotado" if agotado else "Stock bajo",
            }
        )

    # Agotados first, then lowest stock first.
    rows.sort(key=lambda r: (r["estado"] != "Agotado", r["stock"]))
    return rows


def _request_button(ctx: dict, row: dict, already_open: bool) -> None:
    """Render the 'Solicitar Reposición' control for a single alert row."""
    if already_open:
        st.success("Solicitud enviada", icon="✅")
        return
    if st.button(
        "Solicitar Reposición",
        key=f"repo_btn_{row['id']}",
        use_container_width=True,
    ):
        try:
            created = db.add_replenishment_request(
                product_id=row["id"],
                codigo=row["codigo"],
                descripcion=row["descripcion"],
                sede=ctx["sede"],
                material_tipo=row["material_tipo"],
                stock_actual=row["stock"],
                stock_minimo=row["minimo"],
                cantidad_sugerida=row["sugerida"],
                solicitado_por=ctx["usuario_rol"],
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"No se pudo crear la solicitud: {exc}")
            return
        if created:
            st.success("Solicitud de reposición creada.")
        else:
            st.info("Ya existe una solicitud abierta para este producto.")
        st.rerun()


def _render_alert(ctx: dict, row: dict, already_open: bool) -> None:
    badge = "🔴 Agotado" if row["estado"] == "Agotado" else "🟠 Stock bajo"
    with st.container(border=True):
        head = st.columns([3, 1])
        with head[0]:
            st.markdown(f"**{row['codigo'] or '—'}** — {row['descripcion']}")
            st.caption(f"Categoría: {row['categoria']} · {badge}")
        with head[1]:
            _request_button(ctx, row, already_open)
        m = st.columns(3)
        m[0].metric("Stock actual", _fmt(row["stock"]))
        m[1].metric("Stock mínimo", _fmt(row["minimo"]))
        m[2].metric("Cantidad sugerida a pedir", _fmt(row["sugerida"]))


def render(ctx: dict) -> None:
    st.header(ctx["title"])
    st.caption(ctx["breadcrumb"])
    st.caption(f"Alertas de inventario para **{ctx['sede']}** (solo esta sede).")

    rows = _alert_rows(ctx)

    agotados = [r for r in rows if r["estado"] == "Agotado"]
    bajos = [r for r in rows if r["estado"] == "Stock bajo"]

    c1, c2, c3 = st.columns(3)
    c1.metric("Agotados", len(agotados))
    c2.metric("Stock bajo", len(bajos))
    c3.metric("Productos a reponer", len(rows))

    st.divider()
    st.subheader("Productos que necesitan reposición")
    if not rows:
        st.success("No hay productos con stock bajo ni agotados en esta sede.")
        return

    open_ids = db.open_replenishment_product_ids(
        sede=ctx["sede"],
        material_tipo=ctx.get("material_tipo"),
    )
    for row in rows:
        _render_alert(ctx, row, row["id"] in open_ids)
