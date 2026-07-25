"""Inventory view for ECOMAJES ERP.

Worker-friendly product list for the current scope (sede + material type):
columns Código / Descripción / Categoría / Unidad / Stock / Estado, with a
search box (código or descripción) and filters by Categoría and Estado. When the
role is allowed to edit, an "Agregar producto" form is also shown.

Stock status uses fixed numeric thresholds (same for all roles):
  🔴 Stock crítico  — stock < 10
  🟡 Stock bajo     — 10 ≤ stock < 20
  🟢 Disponible     — stock ≥ 20
Products in crítico/bajo also show a Reposición button that abre un formulario.
"""

from decimal import Decimal, InvalidOperation

import streamlit as st

from ecomajes import config, db

# Thresholds (fixed, same for all roles).
_CRITICO_MAX = 10   # stock < 10
_BAJO_MAX = 20      # 10 ≤ stock < 20

_LABEL_CRITICO = "🔴 Stock crítico"
_LABEL_BAJO = "🟡 Stock bajo"
_LABEL_DISPONIBLE = "🟢 Disponible"
_ESTADOS = [_LABEL_DISPONIBLE, _LABEL_BAJO, _LABEL_CRITICO]


def _num(value) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def _estado_semaforo(stock: Decimal) -> str:
    """Fixed-threshold status label with emoji (all roles)."""
    if stock < _CRITICO_MAX:
        return _LABEL_CRITICO
    if stock < _BAJO_MAX:
        return _LABEL_BAJO
    return _LABEL_DISPONIBLE


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
                "Estado": _estado_semaforo(stock),
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


def _reposicion_form(p: dict, ctx: dict) -> None:
    """Muestra un formulario completo de solicitud de reposición para el producto p."""
    pid = p["id"]
    form_key = f"repo_form_{pid}"
    stock = _num(p["stock"])
    estado_label = _estado_semaforo(stock)

    # Inicializar estado de apertura del formulario
    if form_key not in st.session_state:
        st.session_state[form_key] = False

    open_ids = db.open_replenishment_product_ids(
        sede=None if ctx["include_all_sedes"] else ctx["sede"],
        material_tipo=ctx["material_tipo"],
    )

    col_info, col_btn = st.columns([4, 1])
    with col_info:
        st.markdown(
            f"**{p.get('codigo') or '—'}** · "
            f"{p.get('descripcion') or p['nombre']} · "
            f"{estado_label} · Stock: **{float(stock)}**"
        )
    with col_btn:
        if pid in open_ids:
            st.button(
                "✅ Solicitado",
                key=f"repo_sent_{pid}",
                disabled=True,
            )
        else:
            if st.button("📦 Reposición", key=f"repo_{pid}"):
                st.session_state[form_key] = True
                st.rerun()

    # Mostrar formulario si fue abierto
    if st.session_state.get(form_key) and pid not in open_ids:
        with st.form(f"repo_detail_form_{pid}", clear_on_submit=False):
            st.markdown("##### 📦 Solicitar Reposición")

            col1, col2 = st.columns(2)
            with col1:
                st.text_input("Código", value=p.get("codigo") or "—", disabled=True, key=f"rc_{pid}")
                st.text_input("Stock actual", value=str(float(stock)), disabled=True, key=f"rs_{pid}")
                st.text_input("Estado", value=estado_label, disabled=True, key=f"re_{pid}")
            with col2:
                st.text_input(
                    "Descripción",
                    value=p.get("descripcion") or p["nombre"],
                    disabled=True,
                    key=f"rd_{pid}",
                )
                st.text_input(
                    "Usuario solicitante",
                    value=ctx.get("usuario") or ctx.get("usuario_rol", ""),
                    disabled=True,
                    key=f"ru_{pid}",
                )
                st.text_input("Sede", value=p["sede"], disabled=True, key=f"rsede_{pid}")

            cantidad_solic = st.number_input(
                "Cantidad solicitada *",
                min_value=1,
                value=1,
                step=1,
                help="Cantidad mínima a solicitar. Debe ser mayor que cero.",
                key=f"rcant_{pid}",
            )
            motivo = st.text_area(
                "Motivo de la solicitud",
                placeholder="Ej: Stock insuficiente para demanda semanal…",
                key=f"rmot_{pid}",
            )

            col_sub, col_can = st.columns(2)
            with col_sub:
                submitted = st.form_submit_button("📤 Enviar solicitud", type="primary", use_container_width=True)
            with col_can:
                cancelled = st.form_submit_button("Cancelar", use_container_width=True)

        if submitted:
            if cantidad_solic <= 0:
                st.error("La cantidad solicitada debe ser mayor que cero.")
            else:
                stock_minimo = _num(p.get("stock_minimo"))
                ok = db.add_replenishment_request(
                    product_id=pid,
                    codigo=p.get("codigo"),
                    descripcion=p.get("descripcion") or p["nombre"],
                    sede=p["sede"],
                    material_tipo=p["material_tipo"],
                    stock_actual=stock,
                    stock_minimo=stock_minimo,
                    cantidad_sugerida=Decimal(str(cantidad_solic)),
                    solicitado_por=ctx.get("usuario_rol", ctx.get("usuario_rol", "")),
                )
                if ok:
                    st.success("✅ Solicitud de reposición enviada a Gerencia.")
                else:
                    st.info("Ya existe una solicitud pendiente para este producto.")
                st.session_state[form_key] = False
                st.rerun()

        if cancelled:
            st.session_state[form_key] = False
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
        rows = [r for r in rows if estado_sel in r["Estado"]]

    if rows:
        st.caption(f"{len(rows)} producto(s)")
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("No se encontraron productos con esos filtros.")

    # --- Reposición section for crítico / bajo products ------------------- #
    alert_products = [
        p for p in products
        if _num(p["stock"]) < _BAJO_MAX
    ]
    if alert_products:
        st.divider()
        st.subheader("⚠️ Productos que requieren reposición")
        for p in alert_products:
            _reposicion_form(p, ctx)

    if ctx["editable"]:
        _add_product_form(ctx)
