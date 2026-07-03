"""Movement registration view for ECOMAJES ERP.

Registers stock movements (entrada / salida / venta) for a product. Each
movement atomically updates the product stock and is recorded for history.
Also shows the most recent movements for the current scope.
"""

from decimal import Decimal

import streamlit as st

from ecomajes import db

_TIPOS = [db.MOVEMENT_ENTRADA, db.MOVEMENT_SALIDA, db.MOVEMENT_VENTA]


def _product_label(p: dict) -> str:
    tipo = db.TIPO_LABELS.get(p["material_tipo"], p["material_tipo"])
    return (
        f"{p['nombre']} · {tipo} · {p['sede']} · "
        f"stock: {float(p['stock'])} {p['unidad']}"
    )


def _recent_movements(ctx: dict) -> None:
    st.subheader("Movimientos recientes")
    movements = db.list_movements(
        sede=ctx["sede"],
        material_tipo=ctx["material_tipo"],
        include_all_sedes=ctx["include_all_sedes"],
        limit=50,
    )
    if not movements:
        st.caption("Sin movimientos registrados.")
        return
    rows = [
        {
            "Fecha": m["created_at"].strftime("%Y-%m-%d %H:%M"),
            "Producto": m["producto"],
            "Sede": m["sede"],
            "Tipo": db.MOVEMENT_LABELS.get(m["tipo"], m["tipo"]),
            "Cantidad": float(m["cantidad"]),
            "Unidad": m["unidad"],
            "Nota": m["nota"] or "—",
        }
        for m in movements
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render(ctx: dict) -> None:
    st.header(ctx["title"])
    st.caption(ctx["breadcrumb"])

    products = db.list_products(
        sede=ctx["sede"],
        material_tipo=ctx["material_tipo"],
        include_all_sedes=ctx["include_all_sedes"],
    )
    if not products:
        st.info("Primero registra productos en el módulo de Inventario.")
        return

    options = {p["id"]: p for p in products}

    with st.form("movement_form", clear_on_submit=True):
        product_id = st.selectbox(
            "Producto",
            list(options.keys()),
            format_func=lambda pid: _product_label(options[pid]),
        )
        col1, col2 = st.columns(2)
        with col1:
            tipo = st.selectbox(
                "Tipo de movimiento",
                _TIPOS,
                format_func=lambda t: db.MOVEMENT_LABELS[t],
            )
        with col2:
            cantidad = st.number_input("Cantidad", min_value=0.001, value=1.0, step=1.0)
        nota = st.text_input("Nota (opcional)")
        submitted = st.form_submit_button("Registrar movimiento")

    if submitted:
        product = options[product_id]
        try:
            new_stock = db.register_movement(
                product_id=product["id"],
                tipo=tipo,
                cantidad=Decimal(str(cantidad)),
                nota=nota.strip(),
                usuario_rol=ctx["usuario_rol"],
                sede=product["sede"],
            )
        except db.StockError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"No se pudo registrar el movimiento: {exc}")
        else:
            st.success(
                f"Movimiento registrado. Nuevo stock de «{product['nombre']}»: "
                f"{float(new_stock)} {product['unidad']}."
            )
            st.rerun()

    st.divider()
    _recent_movements(ctx)
