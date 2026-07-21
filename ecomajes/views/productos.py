"""Product catalog view for ECOMAJES ERP (GERENCIA > Productos).

Lets GERENCIA search, create, edit and activate/deactivate products using the
catalog fields stored on the `products` table (codigo, descripcion, categoria,
unidad, tipo_venta, peso, stock_minimo, observaciones, activo). Cutting
calculations for "corte personalizado" are intentionally not implemented yet.
"""

from decimal import Decimal

import streamlit as st

from ecomajes import db

# Ordered sale-type keys for selectboxes (labels come from db.TIPO_VENTA_LABELS).
_TIPO_VENTA_KEYS = list(db.TIPO_VENTA_LABELS.keys())


def _tipo_venta_label(key: str) -> str:
    return db.TIPO_VENTA_LABELS.get(key, key)


def _display_rows(products: list[dict]) -> list[dict]:
    """Shape catalog rows for the product table."""
    rows = []
    for p in products:
        rows.append(
            {
                "Código": p["codigo"] or "—",
                "Descripción": p["descripcion"] or p["nombre"],
                "Categoría": p["categoria"] or "—",
                "Unidad": p["unidad"],
                "Tipo de venta": _tipo_venta_label(p["tipo_venta"]),
                "Peso": float(p["peso"]) if p["peso"] is not None else None,
                "Stock mínimo": float(p["stock_minimo"]),
                "Observaciones": p["observaciones"] or "—",
                "Estado": "Activo" if p["activo"] else "Inactivo",
                "Sede": p["sede"],
            }
        )
    return rows


def _handle_error(exc: Exception) -> None:
    """Surface a friendly message for common integrity errors."""
    msg = str(exc).lower()
    if "unique" in msg or "duplicate" in msg:
        if "codigo" in msg:
            st.error("Ya existe un producto con ese código.")
        else:
            st.error("Ya existe un producto con esa descripción en esta sede.")
    else:
        st.error(f"No se pudo guardar el producto: {exc}")


def _create_form(ctx: dict) -> None:
    with st.expander("➕ Crear producto"):
        with st.form("create_product_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                codigo = st.text_input("Código")
                categoria = st.text_input("Categoría")
                tipo_venta = st.selectbox(
                    "Tipo de venta",
                    _TIPO_VENTA_KEYS,
                    format_func=_tipo_venta_label,
                )
                stock_minimo = st.number_input(
                    "Stock mínimo", min_value=0.0, value=0.0, step=1.0
                )
            with col2:
                descripcion = st.text_input("Descripción")
                unidad = st.text_input("Unidad", value="unidad")
                peso = st.number_input("Peso", min_value=0.0, value=0.0, step=0.1)
                activo = st.checkbox("Estado activo", value=True)
            observaciones = st.text_area("Observaciones")

            # Target sede: fixed unless consolidated (Empresa Completa).
            if ctx["include_all_sedes"]:
                target_sede = st.selectbox("Sede", ctx["sede_options"])
            else:
                target_sede = ctx["sede"]

            submitted = st.form_submit_button("Guardar producto")

        if submitted:
            if not descripcion.strip():
                st.error("La descripción es obligatoria.")
                return
            try:
                db.create_catalog_product(
                    sede=target_sede,
                    descripcion=descripcion.strip(),
                    codigo=codigo.strip() or None,
                    categoria=categoria.strip() or None,
                    unidad=unidad.strip() or "unidad",
                    tipo_venta=tipo_venta,
                    peso=Decimal(str(peso)),
                    stock_minimo=Decimal(str(stock_minimo)),
                    observaciones=observaciones.strip() or None,
                    activo=activo,
                )
            except Exception as exc:
                _handle_error(exc)
            else:
                db.log_audit(
                    db.AUDIT_PRODUCT_CREATED,
                    "Productos",
                    detalle=f"{descripcion.strip()} ({target_sede})",
                    usuario_rol=ctx["usuario_rol"],
                    sede=target_sede,
                )
                st.success(f"Producto «{descripcion.strip()}» creado.")
                st.rerun()


def _edit_form(ctx: dict, products: list[dict]) -> None:
    if not products:
        return

    with st.expander("✏️ Editar producto"):
        by_id = {p["id"]: p for p in products}
        selected_id = st.selectbox(
            "Producto a editar",
            list(by_id.keys()),
            format_func=lambda i: (
                f"{by_id[i]['codigo'] or '—'} · "
                f"{by_id[i]['descripcion'] or by_id[i]['nombre']}"
            ),
            key="edit_product_select",
        )
        prod = by_id[selected_id]

        with st.form(f"edit_product_form_{selected_id}"):
            col1, col2 = st.columns(2)
            with col1:
                codigo = st.text_input("Código", value=prod["codigo"] or "")
                categoria = st.text_input(
                    "Categoría", value=prod["categoria"] or ""
                )
                current_tipo = (
                    prod["tipo_venta"]
                    if prod["tipo_venta"] in _TIPO_VENTA_KEYS
                    else _TIPO_VENTA_KEYS[0]
                )
                tipo_venta = st.selectbox(
                    "Tipo de venta",
                    _TIPO_VENTA_KEYS,
                    index=_TIPO_VENTA_KEYS.index(current_tipo),
                    format_func=_tipo_venta_label,
                )
                stock_minimo = st.number_input(
                    "Stock mínimo",
                    min_value=0.0,
                    value=float(prod["stock_minimo"]),
                    step=1.0,
                )
            with col2:
                descripcion = st.text_input(
                    "Descripción", value=prod["descripcion"] or ""
                )
                unidad = st.text_input("Unidad", value=prod["unidad"])
                peso = st.number_input(
                    "Peso",
                    min_value=0.0,
                    value=float(prod["peso"]) if prod["peso"] is not None else 0.0,
                    step=0.1,
                )
                activo = st.checkbox("Estado activo", value=prod["activo"])
            observaciones = st.text_area(
                "Observaciones", value=prod["observaciones"] or ""
            )

            submitted = st.form_submit_button("Guardar cambios")

        if submitted:
            if not descripcion.strip():
                st.error("La descripción es obligatoria.")
                return
            try:
                db.update_catalog_product(
                    product_id=selected_id,
                    descripcion=descripcion.strip(),
                    codigo=codigo.strip() or None,
                    categoria=categoria.strip() or None,
                    unidad=unidad.strip() or "unidad",
                    tipo_venta=tipo_venta,
                    peso=Decimal(str(peso)),
                    stock_minimo=Decimal(str(stock_minimo)),
                    observaciones=observaciones.strip() or None,
                    activo=activo,
                )
            except Exception as exc:
                _handle_error(exc)
            else:
                db.log_audit(
                    db.AUDIT_PRODUCT_UPDATED,
                    "Productos",
                    detalle=f"{descripcion.strip()} (ID {selected_id})",
                    usuario_rol=ctx["usuario_rol"],
                    sede=prod["sede"],
                )
                st.success("Producto actualizado.")
                st.rerun()

        # Quick activate / deactivate for the selected product.
        st.divider()
        estado_txt = "Activo" if prod["activo"] else "Inactivo"
        st.caption(f"Estado actual: **{estado_txt}**")
        if prod["activo"]:
            if st.button("🚫 Desactivar producto", key=f"deact_{selected_id}"):
                db.set_product_active(selected_id, False)
                db.log_audit(
                    db.AUDIT_PRODUCT_DEACTIVATED,
                    "Productos",
                    detalle=(
                        f"{prod['descripcion'] or prod['nombre']} "
                        f"(ID {selected_id})"
                    ),
                    usuario_rol=ctx["usuario_rol"],
                    sede=prod["sede"],
                )
                st.success("Producto desactivado.")
                st.rerun()
        else:
            if st.button("✅ Activar producto", key=f"act_{selected_id}"):
                db.set_product_active(selected_id, True)
                db.log_audit(
                    db.AUDIT_PRODUCT_ACTIVATED,
                    "Productos",
                    detalle=(
                        f"{prod['descripcion'] or prod['nombre']} "
                        f"(ID {selected_id})"
                    ),
                    usuario_rol=ctx["usuario_rol"],
                    sede=prod["sede"],
                )
                st.success("Producto activado.")
                st.rerun()


def render(ctx: dict) -> None:
    st.header(ctx["title"])
    st.caption(ctx["breadcrumb"])

    search = st.text_input(
        "🔍 Buscar por código o descripción", key="catalog_search"
    )

    products = db.list_catalog_products(
        sede=ctx["sede"],
        include_all_sedes=ctx["include_all_sedes"],
        search=search.strip() or None,
    )

    if products:
        st.dataframe(
            _display_rows(products), use_container_width=True, hide_index=True
        )
    else:
        st.info("No se encontraron productos.")

    if ctx["editable"]:
        _create_form(ctx)
        _edit_form(ctx, products)
