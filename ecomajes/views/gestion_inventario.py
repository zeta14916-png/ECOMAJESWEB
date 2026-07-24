"""Gestión de Inventario view for ECOMAJES ERP (GERENCIA).

Consolidated, read-only inventory overview. Products are displayed with:
- Stock status color coding per spec:
    🔴 Stock crítico — stock < 10
    🟡 Stock bajo    — stock entre 10 y 19
    🟢 Disponible    — stock >= 20
- Columns: Código, Descripción, Categoría, Unidad, Precio, Stock,
           Estado, Sede, Tipo de material.

Tabs: Material Nuevo | Material Segundo Uso | Empresa Completa.
Scope (Sede Principal / Sucursal / Empresa Completa) is switchable per tab.
Filters: categoría, estado, búsqueda de texto.
"""

import streamlit as st

from ecomajes import config, db

_EMPRESA_COMPLETA = config.SEDE_EMPRESA_COMPLETA
_LOCATIONS = [config.SEDE_PRINCIPAL, config.SEDE_SUCURSAL, _EMPRESA_COMPLETA]

_TODAS = "Todas"
_SIN_CATEGORIA = "(Sin categoría)"

# Stock-level thresholds from the official spec.
_CRITICO_MAX = 10     # stock < 10  → crítico
_BAJO_MAX = 20        # 10 ≤ stock < 20 → bajo


def _num(value) -> float:
    return float(value) if value is not None else 0.0


def _estado(scope_stock: float) -> str:
    """Derive the stock status using the official colour thresholds."""
    if scope_stock < _CRITICO_MAX:
        return "🔴 Stock crítico"
    if scope_stock < _BAJO_MAX:
        return "🟡 Stock bajo"
    return "🟢 Disponible"


def _sede_label(in_principal: bool, in_sucursal: bool) -> str:
    parts = []
    if in_principal:
        parts.append(config.SEDE_PRINCIPAL)
    if in_sucursal:
        parts.append(config.SEDE_SUCURSAL)
    return " / ".join(parts) if parts else "—"


def _fetch_prices() -> dict:
    """Return a {product_id: precio} map from the prices table."""
    try:
        rows = db.list_prices(
            sede=None,
            material_tipo=None,
            include_all_sedes=True,
        )
        return {r["product_id"]: _num(r.get("precio")) for r in rows}
    except Exception:  # noqa: BLE001
        return {}


def _build_rows(scope: str, material_tipo: str | None, prices: dict) -> list[dict]:
    """Fetch combined products and shape them for the current scope and material."""
    raw = db.inventory_overview(config.SEDE_PRINCIPAL, config.SEDE_SUCURSAL)
    rows: list[dict] = []
    for p in raw:
        # Filter by material type tab.
        if material_tipo is not None and p["material_tipo"] != material_tipo:
            continue

        stock_principal = _num(p["stock_principal"])
        stock_sucursal = _num(p["stock_sucursal"])
        stock_total = stock_principal + stock_sucursal

        # Determine the scope-relevant stock value.
        if scope == config.SEDE_PRINCIPAL:
            if not p["in_principal"]:
                continue
            scope_stock = stock_principal
        elif scope == config.SEDE_SUCURSAL:
            if not p["in_sucursal"]:
                continue
            scope_stock = stock_sucursal
        else:  # Empresa Completa
            scope_stock = stock_total

        tipo = p.get("material_tipo") or ""
        tipo_label = db.TIPO_LABELS.get(tipo, tipo or "—")

        # Price: look up by product_id if available.
        precio = prices.get(p.get("id")) if p.get("id") else 0.0

        rows.append(
            {
                "Código": p["codigo"] or "—",
                "Descripción": p["descripcion"] or p["nombre"],
                "Categoría": p["categoria"] or _SIN_CATEGORIA,
                "Unidad": p["unidad"] or "—",
                "Precio": precio,
                "Stock": scope_stock,
                "Estado": _estado(scope_stock),
                "Sede": _sede_label(bool(p["in_principal"]), bool(p["in_sucursal"])),
                "Tipo de material": tipo_label,
                # Hidden for filtering.
                "_codigo": (p["codigo"] or "").lower(),
                "_descripcion": (p["descripcion"] or p["nombre"] or "").lower(),
                "_categoria": p["categoria"] or _SIN_CATEGORIA,
            }
        )
    return rows


def _apply_filters(rows, categoria, estado, search) -> list[dict]:
    term = (search or "").strip().lower()
    out = []
    for r in rows:
        if categoria != _TODAS and r["_categoria"] != categoria:
            continue
        if estado != _TODAS and not r["Estado"].startswith(estado.split()[0]):
            continue
        if term and term not in r["_codigo"] and term not in r["_descripcion"]:
            continue
        out.append(r)
    return out


def _render_inventory(scope: str, material_tipo: str | None, prices: dict) -> None:
    """Render filters + table for a given scope/material combination."""
    rows = _build_rows(scope, material_tipo, prices)

    # ---- Filters ----
    col1, col2, col3 = st.columns(3)
    categorias = [_TODAS] + sorted({r["_categoria"] for r in rows})
    estados_options = [_TODAS, "🔴", "🟡", "🟢"]
    estados_labels = {
        _TODAS: "Todos los estados",
        "🔴": "🔴 Stock crítico",
        "🟡": "🟡 Stock bajo",
        "🟢": "🟢 Disponible",
    }
    key_suffix = f"{scope}_{material_tipo or 'all'}"
    with col1:
        categoria = st.selectbox(
            "Categoría", categorias, key=f"gi_cat_{key_suffix}"
        )
    with col2:
        estado_key = st.selectbox(
            "Estado",
            estados_options,
            format_func=lambda k: estados_labels.get(k, k),
            key=f"gi_est_{key_suffix}",
        )
        estado_filter = _TODAS if estado_key == _TODAS else estados_labels[estado_key]
    with col3:
        search = st.text_input(
            "🔍 Buscar (código o descripción)", key=f"gi_search_{key_suffix}"
        )

    filtered = _apply_filters(rows, categoria, estado_filter, search)

    # ---- Metrics ----
    total = len(filtered)
    criticos = sum(1 for r in filtered if r["Estado"].startswith("🔴"))
    bajos = sum(1 for r in filtered if r["Estado"].startswith("🟡"))
    disponibles = sum(1 for r in filtered if r["Estado"].startswith("🟢"))
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total productos", total)
    m2.metric("🔴 Stock crítico", criticos)
    m3.metric("🟡 Stock bajo", bajos)
    m4.metric("🟢 Disponible", disponibles)

    # ---- Table ----
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
            "Precio": st.column_config.NumberColumn("Precio ($)", format="%.2f"),
            "Stock": st.column_config.NumberColumn(format="%.2f"),
        },
    )


def render(ctx: dict) -> None:
    st.header(ctx["title"])
    st.caption(ctx["breadcrumb"])

    # Load prices once for the entire view.
    prices = _fetch_prices()

    # Scope selector (shared across tabs).
    scope = st.selectbox(
        "Ubicación / Sede", _LOCATIONS, key="gi_scope"
    )

    # Tabs by material type as required by the spec.
    tab_nuevo, tab_msu, tab_todos = st.tabs(
        ["🔩 Material Nuevo", "♻️ Material Segundo Uso", "🏢 Empresa Completa"]
    )

    with tab_nuevo:
        _render_inventory(scope, db.TIPO_NUEVO, prices)

    with tab_msu:
        _render_inventory(scope, db.TIPO_SEGUNDO_USO, prices)

    with tab_todos:
        _render_inventory(scope, None, prices)
