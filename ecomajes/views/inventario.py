"""Inventory view for ECOMAJES ERP.

Lists products for the current scope (sede + material type) and, when the role
is allowed to edit, provides a form to add a new product with initial stock.
"""

from decimal import Decimal, InvalidOperation

import streamlit as st

from ecomajes import config, db


def _clean_rows(products: list[dict]) -> list[dict]:
    """Shape product rows for display."""
    return [
        {
            "Sede": p["sede"],
            "Tipo": db.TIPO_LABELS.get(p["material_tipo"], p["material_tipo"]),
            "Producto": p["nombre"],
            "SKU": p["sku"] or "—",
            "Unidad": p["unidad"],
            "Stock": float(p["stock"]),
        }
        for p in products
    ]


def _add_product_form(ctx) -> None:
    with st.expander("➕ Agregar producto", expanded=ctx["focus_add"]):
        with st.form("add_product_form", clear_on_submit=True):
            nombre = st.text_input("Nombre del producto")
            col1, col2 = st.columns(2)
            with col1:
                sku = st.text_input("SKU (opcional)")
            with col2:
                unidad = st.text_input("Unidad", value="unidad")
            stock_inicial = st.number_input(
                "Stock inicial", min_value=0.0, value=0.0, step=1.0
            )

            # Target sede: fixed unless consolidated (Empresa Completa).
            if ctx["include_all_sedes"]:
                target_sede = st.selectbox("Sede destino", ctx["sede_options"])
            else:
                target_sede = ctx["sede"]

            # Material type: fixed for admin groups, selectable otherwise.
            if ctx["material_tipo"] is not None:
                target_tipo = ctx["material_tipo"]
            else:
                target_tipo = st.selectbox(
                    "Tipo de material",
                    [db.TIPO_NUEVO, db.TIPO_SEGUNDO_USO],
                    format_func=lambda t: db.TIPO_LABELS[t],
                )

            submitted = st.form_submit_button("Guardar producto")

        if submitted:
            if not nombre.strip():
                st.error("El nombre del producto es obligatorio.")
                return
            try:
                db.add_product(
                    sede=target_sede,
                    material_tipo=target_tipo,
                    nombre=nombre.strip(),
                    sku=sku.strip(),
                    unidad=unidad.strip() or "unidad",
                    stock_inicial=Decimal(str(stock_inicial)),
                )
            except InvalidOperation:
                st.error("Stock inicial inválido.")
            except Exception as exc:  # e.g. duplicate (sede, tipo, nombre)
                if "unique" in str(exc).lower() or "duplicate" in str(exc).lower():
                    st.error("Ya existe un producto con ese nombre en esta sede/tipo.")
                else:
                    st.error(f"No se pudo guardar el producto: {exc}")
            else:
                st.success(f"Producto «{nombre.strip()}» agregado.")
                st.rerun()


def render(ctx: dict) -> None:
    st.header(ctx["title"])
    st.caption(ctx["breadcrumb"])

    products = db.list_products(
        sede=ctx["sede"],
        material_tipo=ctx["material_tipo"],
        include_all_sedes=ctx["include_all_sedes"],
    )

    if products:
        st.dataframe(_clean_rows(products), use_container_width=True, hide_index=True)
    else:
        st.info("No hay productos registrados en este ámbito todavía.")

    if ctx["editable"]:
        _add_product_form(ctx)
