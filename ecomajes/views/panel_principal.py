"""Panel Principal (Dashboard) for ECOMAJES ERP — GERENCIA.

Resumen ejecutivo de ventas, stock, caja chica y balance rápido.
Respeta el ámbito seleccionado (Sede Principal / Sucursal / Empresa Completa).
No crea datos de prueba; usa únicamente las fuentes de datos reales.
"""

import calendar
from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
import streamlit as st

from ecomajes import config, db

_EMPRESA_COMPLETA = config.SEDE_EMPRESA_COMPLETA
_LOW = db.LOW_STOCK_THRESHOLD
_CRITICAL = Decimal("1")


def _money(v) -> float:
    return float(v) if v is not None else 0.0


def _fmt(v) -> str:
    return f"S/ {_money(v):,.2f}"


def _scope(sede: str) -> tuple[str | None, bool]:
    if sede == _EMPRESA_COMPLETA:
        return None, True
    return sede, False


def _week_range(ref: date) -> tuple[date, date]:
    start = ref - timedelta(days=ref.weekday())
    return start, start + timedelta(days=6)


def _month_range(ref: date) -> tuple[date, date]:
    last = calendar.monthrange(ref.year, ref.month)[1]
    return ref.replace(day=1), ref.replace(day=last)


def _year_range(ref: date) -> tuple[date, date]:
    return date(ref.year, 1, 1), date(ref.year, 12, 31)


# --------------------------------------------------------------------------- #
# Sección 1 — KPIs de ventas por periodo
# --------------------------------------------------------------------------- #
def _ventas_kpis(sede_filter: str | None, include_all: bool) -> None:
    st.subheader("📊 Ventas por periodo")
    today = date.today()
    wk_from, wk_to = _week_range(today)
    mo_from, mo_to = _month_range(today)
    yr_from, yr_to = _year_range(today)

    day_s = db.financial_summary(sede_filter, include_all, today, today)
    wk_s = db.financial_summary(sede_filter, include_all, wk_from, wk_to)
    mo_s = db.financial_summary(sede_filter, include_all, mo_from, mo_to)
    yr_s = db.financial_summary(sede_filter, include_all, yr_from, yr_to)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🗓️ Hoy", _fmt(day_s["total_revenue"]),
              help=f"{day_s['total_sales']} transacciones")
    c2.metric("📅 Esta semana", _fmt(wk_s["total_revenue"]),
              help=f"{wk_s['total_sales']} transacciones")
    c3.metric("📆 Este mes", _fmt(mo_s["total_revenue"]),
              help=f"{mo_s['total_sales']} transacciones")
    c4.metric("📈 Este año", _fmt(yr_s["total_revenue"]),
              help=f"{yr_s['total_sales']} transacciones")


# --------------------------------------------------------------------------- #
# Sección 2 — Productos más vendidos
# --------------------------------------------------------------------------- #
def _mas_vendidos(sede_filter: str | None, include_all: bool) -> None:
    st.subheader("🏆 Productos más vendidos (mes actual)")
    today = date.today()
    mo_from, mo_to = _month_range(today)
    rows = db.sales_by_product(sede_filter, include_all, mo_from, mo_to,
                               None, order="desc", limit=10)
    if not rows:
        st.caption("Sin ventas en el mes actual.")
        return
    data = [
        {
            "Producto": r["producto"],
            "Sede": r["sede"],
            "Unidades": float(r["unidades"]),
            "Ingresos": _fmt(r["total"]),
        }
        for r in rows
    ]
    st.dataframe(data, use_container_width=True, hide_index=True)


# --------------------------------------------------------------------------- #
# Sección 3 — Alertas de stock
# --------------------------------------------------------------------------- #
def _stock_alertas(sede_filter: str | None, include_all: bool) -> None:
    st.subheader("⚠️ Alertas de inventario")
    inv = db.list_inventory(sede_filter, include_all, None)

    criticos = [p for p in inv if Decimal(str(p["stock"])) <= _CRITICAL]
    bajos = [
        p for p in inv
        if _CRITICAL < Decimal(str(p["stock"])) <= _LOW
    ]

    c1, c2 = st.columns(2)
    c1.metric("🔴 Stock crítico (≤1)", len(criticos))
    c2.metric("🟡 Stock bajo (≤5)", len(bajos))

    if criticos:
        st.markdown("**Stock crítico:**")
        st.dataframe(
            [{"Producto": p["nombre"], "Sede": p["sede"],
              "Stock": float(p["stock"]), "Unidad": p["unidad"]}
             for p in criticos],
            use_container_width=True, hide_index=True,
        )
    if bajos:
        with st.expander(f"Ver productos con stock bajo ({len(bajos)})"):
            st.dataframe(
                [{"Producto": p["nombre"], "Sede": p["sede"],
                  "Stock": float(p["stock"]), "Unidad": p["unidad"]}
                 for p in bajos],
                use_container_width=True, hide_index=True,
            )


# --------------------------------------------------------------------------- #
# Sección 4 — Solicitudes de reposición pendientes
# --------------------------------------------------------------------------- #
def _reposiciones(sede_filter: str | None, include_all: bool) -> None:
    st.subheader("📋 Solicitudes de reposición pendientes")
    reqs = db.list_replenishment_requests(estado=db.REPO_PENDIENTE)

    # Filtrar por sede si no es empresa completa
    if not include_all and sede_filter:
        reqs = [r for r in reqs if r.get("sede") == sede_filter]

    if not reqs:
        st.success("✅ Sin solicitudes pendientes.")
        return

    st.metric("Solicitudes pendientes", len(reqs))
    st.dataframe(
        [{"Producto": r.get("producto") or r.get("product_id"),
          "Sede": r.get("sede", "—"),
          "Cantidad": float(r.get("cantidad_solicitada", 0)),
          "Fecha": str(r.get("created_at", "—"))[:10]}
         for r in reqs],
        use_container_width=True, hide_index=True,
    )


# --------------------------------------------------------------------------- #
# Sección 5 — Caja Chica por sede
# --------------------------------------------------------------------------- #
def _caja_chica(sede_filter: str | None, include_all: bool) -> None:
    st.subheader("🏦 Caja Chica")
    today = date.today()
    mo_from, mo_to = _month_range(today)

    sedes = [config.SEDE_PRINCIPAL, config.SEDE_SUCURSAL] if include_all else [sede_filter]
    for s in sedes:
        registros = db.list_caja_chica(sede=s, include_all_sedes=False,
                                        date_from=mo_from, date_to=mo_to)
        if registros:
            ultimo = registros[0]
            st.markdown(f"**{s}** — Último arqueo: {str(ultimo['fecha'])[:10]}")
            cc1, cc2, cc3 = st.columns(3)
            cc1.metric("Base", _fmt(ultimo["monto_base"]))
            cc2.metric("Contado", _fmt(ultimo["dinero_contado"]))
            cc3.metric("Diferencia", _fmt(ultimo["diferencia"]))
        else:
            st.caption(f"**{s}** — Sin arqueos de caja chica este mes.")


# --------------------------------------------------------------------------- #
# Sección 6 — Balance rápido
# --------------------------------------------------------------------------- #
def _balance_rapido(sede_filter: str | None, include_all: bool) -> None:
    st.subheader("💰 Balance rápido — Mes actual")
    today = date.today()
    mo_from, mo_to = _month_range(today)
    s = db.financial_summary(sede_filter, include_all, mo_from, mo_to)

    pago = db.sales_by_metodo_pago(sede_filter, include_all, mo_from, mo_to)
    efec = pago.get(db.METODO_EFECTIVO, Decimal("0"))
    yape = pago.get(db.METODO_YAPE, Decimal("0"))
    plin = pago.get(db.METODO_PLIN, Decimal("0"))
    trans = pago.get(db.METODO_TRANSFERENCIA, Decimal("0"))

    c1, c2, c3 = st.columns(3)
    c1.metric("Ingresos", _fmt(s["total_revenue"]))
    c2.metric("Egresos", _fmt(s["total_expenses"]))
    net = s["net_income"]
    c3.metric("Utilidad neta", _fmt(net),
              delta=f"{_money(net):+,.2f}",
              delta_color="normal" if net >= 0 else "inverse")

    st.markdown("**Desglose por método de pago:**")
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("💵 Efectivo", _fmt(efec))
    p2.metric("📱 Yape", _fmt(yape))
    p3.metric("📲 Plin", _fmt(plin))
    p4.metric("🏦 Transferencia", _fmt(trans))


# --------------------------------------------------------------------------- #
# Sección 7 — Gráfico de ventas (últimos 30 días)
# --------------------------------------------------------------------------- #
def _grafico_ventas(sede_filter: str | None, include_all: bool) -> None:
    st.subheader("📉 Ventas diarias — Últimos 30 días")
    today = date.today()
    desde = today - timedelta(days=29)
    rows = db.sales_by_day(sede_filter, include_all, desde, today, None)
    if rows:
        df = pd.DataFrame(rows).rename(columns={"dia": "Día", "total": "Ventas"})
        df["Ventas"] = df["Ventas"].apply(_money)
        df = df.set_index("Día")
        st.line_chart(df[["Ventas"]])
    else:
        st.caption("Sin ventas en los últimos 30 días.")


# --------------------------------------------------------------------------- #
# Main render
# --------------------------------------------------------------------------- #
def render(ctx: dict) -> None:
    st.header(ctx["title"])
    st.caption(ctx["breadcrumb"])

    sede = ctx["sede"]
    sede_filter, include_all = _scope(sede)

    st.info(
        f"📍 Ámbito: **{sede}** — Datos actualizados en tiempo real."
    )
    st.divider()

    _ventas_kpis(sede_filter, include_all)
    st.divider()

    col_left, col_right = st.columns([3, 2])
    with col_left:
        _mas_vendidos(sede_filter, include_all)
    with col_right:
        _stock_alertas(sede_filter, include_all)

    st.divider()
    _reposiciones(sede_filter, include_all)
    st.divider()
    _caja_chica(sede_filter, include_all)
    st.divider()
    _balance_rapido(sede_filter, include_all)
    st.divider()
    _grafico_ventas(sede_filter, include_all)
