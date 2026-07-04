"""Reportes view for ECOMAJES ERP (GERENCIA).

Period-based reporting screen. Reuses existing data sources only (sales = venta
movements, expenses, inventory stock, prices) — nothing is duplicated. Supports
Sede Principal, Sucursal and Empresa Completa (combined), and Día / Semana / Mes
/ Año periods.

It shows financial + inventory metrics, key tables (movements, low/out of stock,
most/least sold), a set of charts, and Excel/PDF export of the same report.
"""

import calendar
from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal

import pandas as pd
import streamlit as st

from ecomajes import config, db, reporting

_EMPRESA_COMPLETA = config.SEDE_EMPRESA_COMPLETA
_LOCATIONS = [config.SEDE_PRINCIPAL, config.SEDE_SUCURSAL, _EMPRESA_COMPLETA]
_PERIODOS = ["Día", "Semana", "Mes", "Año"]
_TODAS = "Todas"


def _money(value) -> float:
    return float(value) if value is not None else 0.0


def _scope(ubicacion: str) -> tuple[str | None, bool]:
    if ubicacion == _EMPRESA_COMPLETA:
        return None, True
    return ubicacion, False


def _period_range(periodo: str, ref: date) -> tuple[date, date]:
    if periodo == "Día":
        return ref, ref
    if periodo == "Semana":
        start = ref - timedelta(days=ref.weekday())
        return start, start + timedelta(days=6)
    if periodo == "Mes":
        last = calendar.monthrange(ref.year, ref.month)[1]
        return ref.replace(day=1), ref.replace(day=last)
    # Año
    return date(ref.year, 1, 1), date(ref.year, 12, 31)


# --------------------------------------------------------------------------- #
# Filters
# --------------------------------------------------------------------------- #
def _filters() -> dict:
    today = date.today()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        ubicacion = st.selectbox("Ubicación", _LOCATIONS, key="rep_ubicacion")
    with col2:
        periodo = st.selectbox("Período", _PERIODOS, index=2, key="rep_periodo")
    with col3:
        ref = st.date_input("Fecha de referencia", value=today, key="rep_ref")
    sede, include_all = _scope(ubicacion)
    with col4:
        categorias = [_TODAS] + db.list_categories(sede, include_all)
        categoria = st.selectbox("Categoría", categorias, key="rep_categoria")

    date_from, date_to = _period_range(periodo, ref)
    return {
        "ubicacion": ubicacion,
        "sede": sede,
        "include_all": include_all,
        "periodo": periodo,
        "ref": ref,
        "date_from": date_from,
        "date_to": date_to,
        "categoria": None if categoria == _TODAS else categoria,
    }


# --------------------------------------------------------------------------- #
# Data gathering (single source for screen + exports; no duplication)
# --------------------------------------------------------------------------- #
def _product_labels(rows: list[dict]) -> list[str]:
    names = Counter(r["producto"] for r in rows)
    labels = []
    for r in rows:
        if names[r["producto"]] > 1:
            labels.append(f"{r['producto']} · {r['sede']} · {r['material_tipo']}")
        else:
            labels.append(r["producto"])
    return labels


def _gather(f: dict) -> dict:
    sede, inc = f["sede"], f["include_all"]
    dfrom, dto, cat = f["date_from"], f["date_to"], f["categoria"]

    summary = db.financial_summary(
        sede=sede, include_all_sedes=inc, date_from=dfrom, date_to=dto
    )

    inv = db.list_inventory(sede, inc, cat)
    agotados = [p for p in inv if Decimal(p["stock"]) <= 0]
    bajo = [
        p for p in inv
        if Decimal("0") < Decimal(p["stock"]) <= db.LOW_STOCK_THRESHOLD
    ]

    most = db.sales_by_product(sede, inc, dfrom, dto, cat, order="desc", limit=10)
    least = db.sales_by_product(sede, inc, dfrom, dto, cat, order="asc", limit=10)
    movs = db.list_movements_range(sede, inc, dfrom, dto, limit=500)

    by_day = db.sales_by_day(sede, inc, dfrom, dto, cat)
    by_month = db.sales_by_month(sede, inc, dfrom, dto, cat)
    by_location = db.sales_by_location(dfrom, dto, cat)
    sales_m = db.sales_by_month(sede, inc, dfrom, dto, None)
    exp_m = db.expenses_by_month(sede, inc, dfrom, dto)

    # Income vs expenses (merge by month).
    ive: dict[str, dict] = {}
    for r in sales_m:
        ive.setdefault(r["mes"], {"Ingresos": 0.0, "Gastos": 0.0})
        ive[r["mes"]]["Ingresos"] = _money(r["total"])
    for r in exp_m:
        ive.setdefault(r["mes"], {"Ingresos": 0.0, "Gastos": 0.0})
        ive[r["mes"]]["Gastos"] = _money(r["total"])

    # Inventory by category.
    inv_cat: dict[str, float] = {}
    for p in inv:
        inv_cat[p["categoria"]] = inv_cat.get(p["categoria"], 0.0) + float(p["stock"])

    # ---- Display-ready tables (also used verbatim by the exports) --------- #
    kpis = [
        {"Métrica": "Total de ventas (transacciones)", "Valor": str(summary["total_sales"])},
        {"Métrica": "Total productos vendidos", "Valor": f"{float(summary['total_products']):g}"},
        {"Métrica": "Ingresos totales", "Valor": f"$ {_money(summary['total_revenue']):,.2f}"},
        {"Métrica": "Gastos totales", "Valor": f"$ {_money(summary['total_expenses']):,.2f}"},
        {"Métrica": "Utilidad neta", "Valor": f"$ {_money(summary['net_income']):,.2f}"},
        {"Métrica": "Productos con stock bajo", "Valor": str(len(bajo))},
        {"Métrica": "Productos agotados", "Valor": str(len(agotados))},
    ]

    most_labels = _product_labels(most)
    least_labels = _product_labels(least)

    tables = {
        "Movimientos de inventario": [
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
        "Productos con stock bajo": [
            {
                "Producto": p["nombre"],
                "Sede": p["sede"],
                "Categoría": p["categoria"],
                "Stock": float(p["stock"]),
                "Unidad": p["unidad"],
            }
            for p in bajo
        ],
        "Productos agotados": [
            {
                "Producto": p["nombre"],
                "Sede": p["sede"],
                "Categoría": p["categoria"],
                "Unidad": p["unidad"],
            }
            for p in agotados
        ],
        "Productos más vendidos": [
            {"Producto": lbl, "Unidades": float(r["unidades"]), "Ingresos": _money(r["total"])}
            for lbl, r in zip(most_labels, most)
        ],
        "Productos menos vendidos": [
            {"Producto": lbl, "Unidades": float(r["unidades"]), "Ingresos": _money(r["total"])}
            for lbl, r in zip(least_labels, least)
        ],
        "Ventas por día": [
            {"Día": str(r["dia"]), "Ventas": _money(r["total"])} for r in by_day
        ],
        "Ventas por mes": [
            {"Mes": r["mes"], "Ventas": _money(r["total"])} for r in by_month
        ],
        "Ventas por sede": [
            {"Sede": r["sede"], "Ventas": _money(r["total"])} for r in by_location
        ],
        "Ingresos vs Gastos": [
            {"Mes": m, "Ingresos": v["Ingresos"], "Gastos": v["Gastos"]}
            for m, v in sorted(ive.items())
        ],
        "Inventario por categoría": [
            {"Categoría": c, "Stock": s} for c, s in sorted(inv_cat.items())
        ],
    }

    return {
        "meta": {
            "ubicacion": f["ubicacion"],
            "periodo": f["periodo"],
            "date_from": f["date_from"],
            "date_to": f["date_to"],
            "categoria": f["categoria"] or _TODAS,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        },
        "kpis": kpis,
        "tables": tables,
    }


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def _kpis(report: dict) -> None:
    k = {row["Métrica"]: row["Valor"] for row in report["kpis"]}
    r1 = st.columns(4)
    r1[0].metric("Total de ventas", k["Total de ventas (transacciones)"])
    r1[1].metric("Productos vendidos", k["Total productos vendidos"])
    r1[2].metric("Ingresos totales", k["Ingresos totales"])
    r1[3].metric("Gastos totales", k["Gastos totales"])
    r2 = st.columns(4)
    r2[0].metric("Utilidad neta", k["Utilidad neta"])
    r2[1].metric("Stock bajo", k["Productos con stock bajo"])
    r2[2].metric("Agotados", k["Productos agotados"])


def _table_block(report: dict, name: str) -> None:
    st.markdown(f"**{name}**")
    rows = report["tables"].get(name, [])
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.caption("Sin datos.")


def _bar(report: dict, name: str, index: str, value: str, kind: str = "bar") -> None:
    st.markdown(f"**{name}**")
    rows = report["tables"].get(name, [])
    if not rows:
        st.caption("Sin datos.")
        return
    df = pd.DataFrame(rows).set_index(index)
    if kind == "line":
        st.line_chart(df[[value]])
    else:
        st.bar_chart(df[[value]])


def _charts(report: dict) -> None:
    st.subheader("Gráficos")
    a1, a2 = st.columns(2)
    with a1:
        _bar(report, "Ventas por día", "Día", "Ventas", kind="line")
    with a2:
        _bar(report, "Ventas por mes", "Mes", "Ventas")
    b1, b2 = st.columns(2)
    with b1:
        _bar(report, "Productos más vendidos", "Producto", "Unidades")
    with b2:
        _bar(report, "Productos menos vendidos", "Producto", "Unidades")
    c1, c2 = st.columns(2)
    with c1:
        _bar(report, "Ventas por sede", "Sede", "Ventas")
    with c2:
        st.markdown("**Ingresos vs Gastos**")
        rows = report["tables"].get("Ingresos vs Gastos", [])
        if rows:
            st.bar_chart(pd.DataFrame(rows).set_index("Mes")[["Ingresos", "Gastos"]])
        else:
            st.caption("Sin datos.")
    _bar(report, "Inventario por categoría", "Categoría", "Stock")


def _exports(report: dict) -> None:
    st.subheader("Exportar")
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    col1, col2 = st.columns(2)
    try:
        xlsx = reporting.build_excel(report)
        col1.download_button(
            "⬇️ Excel",
            data=xlsx,
            file_name=f"reporte_ecomajes_{stamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    except Exception as exc:  # noqa: BLE001
        col1.error(f"No se pudo generar el Excel: {exc}")
    try:
        pdf = reporting.build_pdf(report)
        col2.download_button(
            "⬇️ PDF",
            data=pdf,
            file_name=f"reporte_ecomajes_{stamp}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    except Exception as exc:  # noqa: BLE001
        col2.error(f"No se pudo generar el PDF: {exc}")


def render(ctx: dict) -> None:
    st.header(ctx["title"])
    st.caption(ctx["breadcrumb"])

    f = _filters()
    st.caption(
        f"Reporte de **{f['ubicacion']}** · {f['periodo']} · "
        f"{f['date_from']} → {f['date_to']} · Categoría: {f['categoria'] or _TODAS}"
    )
    report = _gather(f)

    st.divider()
    _kpis(report)
    st.divider()
    _charts(report)
    st.divider()

    st.subheader("Detalle")
    _table_block(report, "Movimientos de inventario")
    col1, col2 = st.columns(2)
    with col1:
        _table_block(report, "Productos con stock bajo")
    with col2:
        _table_block(report, "Productos agotados")
    col3, col4 = st.columns(2)
    with col3:
        _table_block(report, "Productos más vendidos")
    with col4:
        _table_block(report, "Productos menos vendidos")

    st.divider()
    _exports(report)
