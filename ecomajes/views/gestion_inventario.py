"""Gestión de Inventario view for ECOMAJES ERP (GERENCIA).

Consolidated, read-only inventory overview. Products held in more than one sede
are combined into a single row (grouped by material type + name) so nothing is
duplicated. For each product it shows stock per sede, the combined total, the
configured minimum stock and a derived status (OK / Stock bajo / Agotado).

Scope (Sede Principal / Sucursal / Empresa Completa) plus category, status and a
text search let GERENCIA slice the list. Empresa Completa combines both sedes.

Reuses existing product data only — it does not create, edit or delete anything.
"""

import streamlit as st

from ecomajes import config, db

_EMPRESA_COMPLETA = config.SEDE_EMPRESA_COMPLETA
_LOCATIONS = [config.SEDE_PRINCIPAL, config.SEDE_SUCURSAL, _EMPRESA_COMPLETA]

_ESTADO_OK = "OK"
_ESTADO_BAJO = "Stock bajo"
_ESTADO_AGOTADO = "Agotado"
_ESTADOS = [_ESTADO_OK, _ESTADO_BAJO, _ESTADO_AGOTADO]

_TODAS = "Todas"
_SIN_CATEGORIA = "(Sin categoría)"


def _num(value) -> float:
    return float(value) if value is not None else 0.0


def _estado(scope_stock: float, stock_minimo: float) -> str:
    """Derive the stock status for the stock relevant to the current scope."""
    if scope_stock <= 0:
        return _ESTADO_AGOTADO
    if scope_stock <= stock_minimo:
        return _ESTADO_BAJO
    return _ESTADO_OK


def _build_rows(scope: str) -> list[dict]:
    """Fetch combined products and shape them for the current scope."""
    raw = db.inventory_overview(config.SEDE_PRINCIPAL, config.SEDE_SUCURSAL)
    rows: list[dict] = []
    for p in raw:
        stock_principal = _num(p["stock_principal"])
        stock_sucursal = _num(p["stock_sucursal"])
        stock_total = stock_principal + stock_sucursal
        stock_minimo = _num(p["stock_minimo"])

        # Include the product only if it belongs to the selected scope.
        if scope == config.SEDE_PRINCIPAL:
            if not p["in_principal"]:
                continue
            scope_stock = stock_principal
        elif scope == config.SEDE_SUCURSAL:
            if not p["in_sucursal"]:
                continue
            scope_stock = stock_sucursal
        else:  # Empresa Completa -> combined
            scope_stock = stock_total

        rows.append(
            {
                "Código": p["codigo"] or "—",
                "Descripción": p["descripcion"] or p["nombre"],
                "Categoría": p["categoria"] or _SIN_CATEGORIA,
                "Unidad": p["unidad"] or "—",
                "Stock Sede Principal": stock_principal,
                "Stock Sucursal": stock_sucursal,
                "Stock Total": stock_total,
                "Stock mínimo": stock_minimo,
                "Estado": _estado(scope_stock, stock_minimo),
                # Raw fields for filtering (dropped before display).
                "_codigo": (p["codigo"] or "").lower(),
                "_descripcion": (p["descripcion"] or p["nombre"] or "").lower(),
            }
        )
    return rows


def _apply_filters(rows, categoria, estado, search) -> list[dict]:
    term = (search or "").strip().lower()
    out = []
    for r in rows:
        if categoria != _TODAS and r["Categoría"] != categoria:
            continue
        if estado != _TODAS and r["Estado"] != estado:
            continue
        if term and term not in r["_codigo"] and term not in r["_descripcion"]:
            continue
        out.append(r)
    return out


def render(ctx: dict) -> None:
    st.header(ctx["title"])
    st.caption(ctx["breadcrumb"])

    # --- Filters --------------------------------------------------------- #
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        scope = st.selectbox("Ubicación", _LOCATIONS, key="gi_scope")
    rows = _build_rows(scope)
    categorias = [_TODAS] + sorted({r["Categoría"] for r in rows})
    with col2:
        categoria = st.selectbox("Categoría", categorias, key="gi_categoria")
    with col3:
        estado = st.selectbox("Estado", [_TODAS] + _ESTADOS, key="gi_estado")
    with col4:
        search = st.text_input("Buscar (código o descripción)", key="gi_search")

    filtered = _apply_filters(rows, categoria, estado, search)

    # --- Summary metrics ------------------------------------------------- #
    total = len(filtered)
    bajos = sum(1 for r in filtered if r["Estado"] == _ESTADO_BAJO)
    agotados = sum(1 for r in filtered if r["Estado"] == _ESTADO_AGOTADO)
    m1, m2, m3 = st.columns(3)
    m1.metric("Productos", total)
    m2.metric("Stock bajo", bajos)
    m3.metric("Agotados", agotados)

    # --- Table ----------------------------------------------------------- #
    if not filtered:
        st.info("No hay productos que coincidan con los filtros seleccionados.")
        return

    display = [
        {k: v for k, v in r.items() if not k.startswith("_")} for r in filtered
    ]
    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Stock Sede Principal": st.column_config.NumberColumn(format="%.2f"),
            "Stock Sucursal": st.column_config.NumberColumn(format="%.2f"),
            "Stock Total": st.column_config.NumberColumn(format="%.2f"),
            "Stock mínimo": st.column_config.NumberColumn(format="%.2f"),
        },
    )
