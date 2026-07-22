"""Balance Financiero + Dashboard view for ECOMAJES ERP (GERENCIA).

Single-screen financial dashboard. Reuses existing data sources only (sales =
venta movements, expenses, inventory stock, configured prices) — no data is
duplicated. Supports Sede Principal, Sucursal and Empresa Completa (combined).

Layout: filters → KPI cards → charts → alerts. HR payments stay a placeholder
(Recursos Humanos is not implemented here).
"""

from collections import Counter
from datetime import date
from decimal import Decimal

import pandas as pd
import streamlit as st

from ecomajes import config, db

_EMPRESA_COMPLETA = config.SEDE_EMPRESA_COMPLETA
_LOCATIONS = [config.SEDE_PRINCIPAL, config.SEDE_SUCURSAL, _EMPRESA_COMPLETA]
_TODAS = "Todas"


def _money(value) -> float:
    return float(value) if value is not None else 0.0


def _scope(ubicacion: str) -> tuple[str | None, bool]:
    if ubicacion == _EMPRESA_COMPLETA:
        return None, True
    return ubicacion, False


# --------------------------------------------------------------------------- #
# Filters
# --------------------------------------------------------------------------- #
def _filters() -> dict:
    today = date.today()
    month_start = today.replace(day=1)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        ubicacion = st.selectbox("Ubicación", _LOCATIONS)
    with col2:
        date_from = st.date_input("Desde", value=month_start)
    with col3:
        date_to = st.date_input("Hasta", value=today)
    sede, include_all = _scope(ubicacion)
    with col4:
        categorias = [_TODAS] + db.list_categories(sede, include_all)
        categoria = st.selectbox("Categoría", categorias)

    if date_from > date_to:
        st.warning("El rango de fechas es inválido: 'Desde' es posterior a 'Hasta'.")
        date_from, date_to = date_to, date_from

    return {
        "ubicacion": ubicacion,
        "sede": sede,
        "include_all": include_all,
        "date_from": date_from,
        "date_to": date_to,
        "categoria": None if categoria == _TODAS else categoria,
        "today": today,
        "month_start": month_start,
    }


# --------------------------------------------------------------------------- #
# KPI cards
# --------------------------------------------------------------------------- #
def _kpi_cards(f: dict) -> None:
    fin_dia = db.financial_summary(
        sede=f["sede"],
        include_all_sedes=f["include_all"],
        date_from=f["today"],
        date_to=f["today"],
    )
    fin_mes = db.financial_summary(
        sede=f["sede"],
        include_all_sedes=f["include_all"],
        date_from=f["month_start"],
        date_to=f["today"],
    )
    inv = db.list_inventory(sede=f["sede"], include_all_sedes=f["include_all"])
    agotados = [p for p in inv if Decimal(p["stock"]) <= 0]
    bajo = [
        p
        for p in inv
        if Decimal("0") < Decimal(p["stock"]) <= db.LOW_STOCK_THRESHOLD
    ]

    st.caption(
        f"Indicadores para **{f['ubicacion']}** "
        "(ventas/gastos del día y del mes en curso)."
    )
    r1 = st.columns(4)
    r1[0].metric("Ventas del día", f"$ {_money(fin_dia['total_revenue']):,.2f}")
    r1[1].metric("Ventas del mes", f"$ {_money(fin_mes['total_revenue']):,.2f}")
    r1[2].metric("Gastos del día", f"$ {_money(fin_dia['total_expenses']):,.2f}")
    r1[3].metric("Gastos del mes", f"$ {_money(fin_mes['total_expenses']):,.2f}")

    r2 = st.columns(4)
    r2[0].metric("Utilidad neta (mes)", f"$ {_money(fin_mes['net_income']):,.2f}")
    r2[1].metric("Productos vendidos (mes)", f"{float(fin_mes['total_products']):g}")
    r2[2].metric("Productos con stock bajo", len(bajo))
    r2[3].metric("Productos agotados", len(agotados))


# --------------------------------------------------------------------------- #
# Charts
# --------------------------------------------------------------------------- #
def _chart_sales_by_day(f: dict) -> None:
    st.markdown("**Ventas por día**")
    rows = db.sales_by_day(
        f["sede"], f["include_all"], f["date_from"], f["date_to"], f["categoria"]
    )
    if not rows:
        st.caption("Sin datos.")
        return
    df = pd.DataFrame(
        {str(r["dia"]): _money(r["total"]) for r in rows}.items(),
        columns=["Día", "Ventas"],
    ).set_index("Día")
    st.line_chart(df)


def _chart_sales_by_month(f: dict) -> None:
    st.markdown("**Ventas por mes**")
    rows = db.sales_by_month(
        f["sede"], f["include_all"], f["date_from"], f["date_to"], f["categoria"]
    )
    if not rows:
        st.caption("Sin datos.")
        return
    df = pd.DataFrame(
        {r["mes"]: _money(r["total"]) for r in rows}.items(),
        columns=["Mes", "Ventas"],
    ).set_index("Mes")
    st.bar_chart(df)


def _product_labels(rows: list[dict]) -> list[str]:
    """Unique display labels; disambiguate products that share a name."""
    names = Counter(r["producto"] for r in rows)
    labels = []
    for r in rows:
        if names[r["producto"]] > 1:
            labels.append(f"{r['producto']} · {r['sede']} · {r['material_tipo']}")
        else:
            labels.append(r["producto"])
    return labels


def _chart_products(f: dict, order: str, title: str) -> None:
    st.markdown(f"**{title}**")
    rows = db.sales_by_product(
        f["sede"],
        f["include_all"],
        f["date_from"],
        f["date_to"],
        f["categoria"],
        order=order,
        limit=10,
    )
    if not rows:
        st.caption("Sin datos.")
        return
    labels = _product_labels(rows)
    df = pd.DataFrame(
        {"Producto": labels, "Unidades": [float(r["unidades"]) for r in rows]}
    ).set_index("Producto")
    st.bar_chart(df)


def _chart_sales_by_location(f: dict) -> None:
    st.markdown("**Ventas por sede**")
    rows = db.sales_by_location(f["date_from"], f["date_to"], f["categoria"])
    if not rows:
        st.caption("Sin datos.")
        return
    df = pd.DataFrame(
        {r["sede"]: _money(r["total"]) for r in rows}.items(),
        columns=["Sede", "Ventas"],
    ).set_index("Sede")
    st.bar_chart(df)


def _chart_income_vs_expenses(f: dict) -> None:
    st.markdown("**Ingresos vs Gastos (por mes)**")
    sales = db.sales_by_month(
        f["sede"], f["include_all"], f["date_from"], f["date_to"], None
    )
    expenses = db.expenses_by_month(
        f["sede"], f["include_all"], f["date_from"], f["date_to"]
    )
    if not sales and not expenses:
        st.caption("Sin datos.")
        return
    data: dict[str, dict] = {}
    for r in sales:
        data.setdefault(r["mes"], {"Ingresos": 0.0, "Gastos": 0.0})
        data[r["mes"]]["Ingresos"] = _money(r["total"])
    for r in expenses:
        data.setdefault(r["mes"], {"Ingresos": 0.0, "Gastos": 0.0})
        data[r["mes"]]["Gastos"] = _money(r["total"])
    df = pd.DataFrame(
        [{"Mes": m, **v} for m, v in sorted(data.items())]
    ).set_index("Mes")
    st.bar_chart(df)


def _chart_inventory_by_category(f: dict) -> None:
    st.markdown("**Inventario por categoría**")
    inv = db.list_inventory(f["sede"], f["include_all"], f["categoria"])
    if not inv:
        st.caption("Sin datos.")
        return
    totals: dict[str, float] = {}
    for p in inv:
        totals[p["categoria"]] = totals.get(p["categoria"], 0.0) + float(p["stock"])
    df = pd.DataFrame(
        totals.items(), columns=["Categoría", "Stock"]
    ).set_index("Categoría")
    st.bar_chart(df)


def _charts(f: dict) -> None:
    st.subheader("Gráficos")
    a1, a2 = st.columns(2)
    with a1:
        _chart_sales_by_day(f)
    with a2:
        _chart_sales_by_month(f)
    b1, b2 = st.columns(2)
    with b1:
        _chart_products(f, "desc", "Productos más vendidos")
    with b2:
        _chart_products(f, "asc", "Productos menos vendidos")
    c1, c2 = st.columns(2)
    with c1:
        _chart_sales_by_location(f)
    with c2:
        _chart_income_vs_expenses(f)
    _chart_inventory_by_category(f)


# --------------------------------------------------------------------------- #
# Alerts
# --------------------------------------------------------------------------- #
def _alerts(f: dict) -> None:
    st.subheader("Alertas")
    inv = db.list_inventory(f["sede"], f["include_all"], f["categoria"])
    agotados = [p for p in inv if Decimal(p["stock"]) <= 0]
    bajo = [
        p
        for p in inv
        if Decimal("0") < Decimal(p["stock"]) <= db.LOW_STOCK_THRESHOLD
    ]

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Stock bajo**")
        if bajo:
            st.dataframe(
                [
                    {
                        "Producto": p["nombre"],
                        "Sede": p["sede"],
                        "Categoría": p["categoria"],
                        "Stock": float(p["stock"]),
                        "Unidad": p["unidad"],
                    }
                    for p in bajo
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("Sin productos con stock bajo.")
    with col2:
        st.markdown("**Agotados**")
        if agotados:
            st.dataframe(
                [
                    {
                        "Producto": p["nombre"],
                        "Sede": p["sede"],
                        "Categoría": p["categoria"],
                        "Unidad": p["unidad"],
                    }
                    for p in agotados
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("Sin productos agotados.")

    st.markdown("**Comentarios pendientes**")
    st.info("Sección de comentarios pendiente de implementar.")

    st.markdown("**Últimos movimientos**")
    movs = db.list_movements(
        sede=f["sede"], include_all_sedes=f["include_all"], limit=10
    )
    if movs:
        st.dataframe(
            [
                {
                    "Fecha": m["created_at"].strftime("%Y-%m-%d %H:%M"),
                    "Producto": m["producto"],
                    "Sede": m["sede"],
                    "Tipo": db.MOVEMENT_LABELS.get(m["tipo"], m["tipo"]),
                    "Cantidad": float(m["cantidad"]),
                    "Unidad": m["unidad"],
                }
                for m in movs
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("Sin movimientos recientes.")


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def render(ctx: dict) -> None:
    st.header(ctx["title"])
    st.caption(ctx["breadcrumb"])

    f = _filters()
    st.caption(
        f"Rango de gráficos: {f['date_from']} → {f['date_to']} · "
        f"Categoría: {f['categoria'] or _TODAS}"
    )
    st.divider()
    _kpi_cards(f)
    st.divider()
    _charts(f)
    st.divider()
    _alerts(f)
