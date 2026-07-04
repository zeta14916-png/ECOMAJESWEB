"""Inventory view for ECOMAJES ERP.

Worker-friendly product list for the current scope (sede + material type):
columns Código / Descripción / Categoría / Unidad / Stock / Estado, with a
search box (código or descripción) and filters by Categoría and Estado. When the
role is allowed to edit, an "Agregar producto" form is also shown.
"""

from decimal import Decimal, InvalidOperation

import streamlit as st

from ecomajes import config, db

_ESTADO_DISPONIBLE = "Disponible"
_ESTADO_BAJO = "Stock bajo"
_ESTADO_AGOTADO = "Agotado"
_ESTADOS = [_ESTADO_DISPONIBLE, _ESTADO_BAJO, _ESTADO_AGOTADO]


def _num(value) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def _estado(stock: Decimal, stock_minimo: Decimal) -> str:
    if stock <= 0:
        return _ESTADO_AGOTADO
    if stock_minimo > 0 and stock <= stock_minimo:
        return _ESTADO_BAJO
    return _ESTADO_DISPONIBLE


def _clean_rows(products: list[dict]) -> list[dict]:
    """Shape catalog rows for display (Código/Descripción/Categoría/…/Estado)."""
    rows = []
    for p in products:
        stock = _num(p["stock"])
        rows.append(
            {
                "Código": p.get("codigo") or "—",
                "Descripción": p.get("descripcion") or p["nombre"],
                "Categoría": p.get("categoria") or "—",
                "Unidad": p.get("unidad") or "—",
                "Stock": float(stock),
                "Estado": _estado(stock, _num(p.get("stock_minimo"))),
            }
        )
    return rows


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

    search = st.text_input("🔍 Buscar por código o descripción")

    products = db.list_catalog_products(
        sede=ctx["sede"],
        include_all_sedes=ctx["include_all_sedes"],
        search=search.strip() or None,
        material_tipo=ctx["material_tipo"],
    )

    # Filters (Categoría + Estado). Category options come from the scope.
    categorias = sorted(
        {p.get("categoria") for p in products if p.get("categoria")}
    )
    col1, col2 = st.columns(2)
    with col1:
        categoria_sel = st.selectbox("Categoría", ["Todas", *categorias])
    with col2:
        estado_sel = st.selectbox("Estado", ["Todos", *_ESTADOS])

    rows = _clean_rows(products)
    if categoria_sel != "Todas":
        rows = [r for r in rows if r["Categoría"] == categoria_sel]
    if estado_sel != "Todos":
        rows = [r for r in rows if r["Estado"] == estado_sel]

    if rows:
        st.caption(f"{len(rows)} producto(s)")
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("No se encontraron productos con esos filtros.")

    if ctx["editable"]:
        _add_product_form(ctx)
