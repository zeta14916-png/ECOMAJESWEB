"""Módulo Ventas para ECOMAJES ERP — GERENCIA.

Contiene seis sub-vistas:
  render_diario   → Reporte Diario
  render_semanal  → Reporte Semanal
  render_mensual  → Reporte Mensual
  render_anual    → Reporte Anual
  render_historial  → Historial de Ventas (con filtros)
  render_detalle    → Detalle General de Ventas (totales por método)

Todos respetan el ámbito seleccionado y no modifican módulos anteriores.
No se permite borrar ventas históricas; las anuladas mantienen trazabilidad.
"""

import calendar
from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
import streamlit as st

from ecomajes import config, db

_EMPRESA_COMPLETA = config.SEDE_EMPRESA_COMPLETA
_LOCATIONS = [config.SEDE_PRINCIPAL, config.SEDE_SUCURSAL, _EMPRESA_COMPLETA]
_METODOS_LABEL = db.METODO_PAGO_LABELS
_METODOS_KEYS = db.METODO_PAGO_OPTIONS


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


def _period_range(periodo: str, ref: date) -> tuple[date, date]:
    if periodo == "Día":
        return ref, ref
    if periodo == "Semana":
        return _week_range(ref)
    if periodo == "Mes":
        return _month_range(ref)
    return _year_range(ref)


# --------------------------------------------------------------------------- #
# Componentes compartidos
# --------------------------------------------------------------------------- #
def _render_kpis(sede_f: str | None, inc_all: bool, dfrom: date, dto: date) -> None:
    s = db.financial_summary(sede_f, inc_all, dfrom, dto)
    pago = db.sales_by_metodo_pago(sede_f, inc_all, dfrom, dto)

    c1, c2, c3 = st.columns(3)
    c1.metric("Total de ventas", s["total_sales"])
    c2.metric("Productos vendidos", f"{float(s['total_products']):g}")
    c3.metric("Total vendido", _fmt(s["total_revenue"]))

    p1, p2, p3, p4 = st.columns(4)
    p1.metric("💵 Efectivo", _fmt(pago.get(db.METODO_EFECTIVO, Decimal("0"))))
    p2.metric("📱 Yape", _fmt(pago.get(db.METODO_YAPE, Decimal("0"))))
    p3.metric("📲 Plin", _fmt(pago.get(db.METODO_PLIN, Decimal("0"))))
    p4.metric("🏦 Transferencia", _fmt(pago.get(db.METODO_TRANSFERENCIA, Decimal("0"))))


def _render_tabla_ventas(sede_f: str | None, inc_all: bool,
                          dfrom: date, dto: date) -> None:
    sales = db.list_sales(sede=sede_f, include_all_sedes=inc_all,
                          date_from=dfrom, date_to=dto)
    if not sales:
        st.caption("Sin ventas en este periodo.")
        return

    rows = [
        {
            "#": s["id"],
            "Fecha": str(s["created_at"])[:10],
            "Hora": str(s["created_at"])[11:16],
            "Usuario": s["usuario_rol"] or "—",
            "Sede": s["sede"],
            "Producto": s["producto"],
            "Cantidad": float(s["cantidad"]),
            "Unidad": s["unidad"],
            "P. Unit.": _money(s["precio_unitario"]),
            "Total": _money(s["precio_total"]),
            "Método pago": _METODOS_LABEL.get(s.get("metodo_pago"), s.get("metodo_pago") or "—"),
        }
        for s in sales
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.caption(f"**{len(rows)}** registros encontrados.")


# --------------------------------------------------------------------------- #
# Vistas por periodo (Diario / Semanal / Mensual / Anual)
# --------------------------------------------------------------------------- #
def _render_periodo(ctx: dict, periodo: str) -> None:
    """Reporte de ventas para un periodo fijo."""
    st.header(ctx["title"])
    st.caption(ctx["breadcrumb"])

    sede = ctx["sede"]
    sede_filter, include_all = _scope(sede)

    today = date.today()
    dfrom, dto = _period_range(periodo, today)

    # Selector de fecha de referencia
    ref = st.date_input("Fecha de referencia", value=today,
                        key=f"rep_{periodo}_ref")
    dfrom, dto = _period_range(periodo, ref)

    # Si sede del contexto es empresa completa, también mostrar selector
    if ctx.get("include_all_sedes"):
        sede_sel = st.selectbox("Sede", _LOCATIONS, key=f"rep_{periodo}_sede",
                                index=_LOCATIONS.index(_EMPRESA_COMPLETA))
        sede_filter, include_all = _scope(sede_sel)
    else:
        sede_sel = sede

    st.info(f"📍 **{sede_sel}** · {periodo}: {dfrom} → {dto}")
    st.divider()

    _render_kpis(sede_filter, include_all, dfrom, dto)
    st.divider()
    st.subheader("📦 Detalle de ventas")
    _render_tabla_ventas(sede_filter, include_all, dfrom, dto)


def render_diario(ctx: dict) -> None:
    _render_periodo(ctx, "Día")


def render_semanal(ctx: dict) -> None:
    _render_periodo(ctx, "Semana")


def render_mensual(ctx: dict) -> None:
    _render_periodo(ctx, "Mes")


def render_anual(ctx: dict) -> None:
    _render_periodo(ctx, "Año")


# --------------------------------------------------------------------------- #
# Historial de Ventas
# --------------------------------------------------------------------------- #
def render_historial(ctx: dict) -> None:
    """Historial completo de ventas con filtros exhaustivos."""
    st.header(ctx["title"])
    st.caption(ctx["breadcrumb"])

    sede = ctx["sede"]
    sede_filter_ctx, include_all_ctx = _scope(sede)

    # ── Filtros ────────────────────────────────────────────────────────────── #
    st.subheader("🔍 Filtros")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        fecha_ini = st.date_input("Fecha inicial",
                                  value=date.today().replace(day=1),
                                  key="hist_fi")
    with col2:
        fecha_fin = st.date_input("Fecha final", value=date.today(),
                                  key="hist_ff")
    with col3:
        sede_opts = ["Todas"] + [config.SEDE_PRINCIPAL, config.SEDE_SUCURSAL]
        sede_sel = st.selectbox("Sede", sede_opts, key="hist_sede")
        if not include_all_ctx and sede_filter_ctx:
            # forzar la sede del ámbito si no es empresa completa
            sede_sel = sede_filter_ctx
    with col4:
        metodo_opts = ["Todos"] + list(_METODOS_LABEL.values())
        metodo_sel = st.selectbox("Método de pago", metodo_opts,
                                  key="hist_metodo")

    col5, col6 = st.columns(2)
    with col5:
        producto_filter = st.text_input("Filtrar por producto", key="hist_prod")
    with col6:
        usuario_filter = st.text_input("Filtrar por usuario", key="hist_user")

    # ── Datos ──────────────────────────────────────────────────────────────── #
    # Determinar scope: el filtro de Sede del formulario tiene prioridad sobre
    # el ámbito de sesión cuando el usuario elige una sede específica.
    if sede_sel == "Todas":
        sf, ia = None, True
    else:
        sf, ia = sede_sel, False

    sales = db.list_sales(sede=sf, include_all_sedes=ia,
                          date_from=fecha_ini, date_to=fecha_fin)

    # Filtros en Python
    metodo_inv = {v: k for k, v in _METODOS_LABEL.items()}
    if metodo_sel != "Todos":
        metodo_key = metodo_inv.get(metodo_sel, metodo_sel)
        sales = [s for s in sales if s.get("metodo_pago") == metodo_key]
    if producto_filter.strip():
        q = producto_filter.strip().lower()
        sales = [s for s in sales if q in (s.get("producto") or "").lower()]
    if usuario_filter.strip():
        q = usuario_filter.strip().lower()
        sales = [s for s in sales if q in (s.get("usuario_rol") or "").lower()]

    # ── Tabla ─────────────────────────────────────────────────────────────── #
    st.divider()
    if not sales:
        st.info("No se encontraron ventas con los filtros seleccionados.")
        return

    rows = [
        {
            "N° Venta": s["id"],
            "Fecha": str(s["created_at"])[:10],
            "Hora": str(s["created_at"])[11:16],
            "Usuario": s["usuario_rol"] or "—",
            "Sede": s["sede"],
            "Producto": s["producto"],
            "Unidad": s["unidad"],
            "Cantidad": float(s["cantidad"]),
            "P. Unitario": _money(s["precio_unitario"]),
            "Total": _money(s["precio_total"]),
            "Método pago": _METODOS_LABEL.get(s.get("metodo_pago"),
                                               s.get("metodo_pago") or "—"),
            "Estado": "Activa",
        }
        for s in sales
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    total = sum(_money(s["precio_total"]) for s in sales)
    st.success(
        f"**{len(rows)}** ventas encontradas · Total: **{_fmt(Decimal(str(total)))}**"
    )
    st.caption("⚠️ El historial es de solo lectura. Las ventas no pueden eliminarse.")


# --------------------------------------------------------------------------- #
# Detalle General de Ventas
# --------------------------------------------------------------------------- #
def render_detalle(ctx: dict) -> None:
    """Detalle general con totales consolidados por método de pago."""
    st.header(ctx["title"])
    st.caption(ctx["breadcrumb"])

    sede = ctx["sede"]
    sede_filter_ctx, include_all_ctx = _scope(sede)

    # ── Filtros ────────────────────────────────────────────────────────────── #
    st.subheader("🔍 Filtros")
    col1, col2, col3 = st.columns(3)
    with col1:
        fecha_ini = st.date_input("Fecha inicial",
                                  value=date.today().replace(day=1),
                                  key="det_fi")
    with col2:
        fecha_fin = st.date_input("Fecha final", value=date.today(),
                                  key="det_ff")
    with col3:
        if include_all_ctx:
            sede_opts = ["Empresa Completa"] + [config.SEDE_PRINCIPAL, config.SEDE_SUCURSAL]
            sede_sel = st.selectbox("Sede", sede_opts, key="det_sede")
            if sede_sel == "Empresa Completa":
                sf, ia = None, True
            else:
                sf, ia = sede_sel, False
        else:
            sf, ia = sede_filter_ctx, False
            st.markdown(f"**Sede:** {sede}")

    col4, col5 = st.columns(2)
    with col4:
        metodo_opts = ["Todos"] + list(_METODOS_LABEL.values())
        metodo_sel = st.selectbox("Método de pago", metodo_opts, key="det_metodo")
    with col5:
        producto_filter = st.text_input("Filtrar por producto", key="det_prod")

    # ── Datos ──────────────────────────────────────────────────────────────── #
    sales = db.list_sales(sede=sf, include_all_sedes=ia,
                          date_from=fecha_ini, date_to=fecha_fin)

    metodo_inv = {v: k for k, v in _METODOS_LABEL.items()}
    if metodo_sel != "Todos":
        metodo_key = metodo_inv.get(metodo_sel, metodo_sel)
        sales = [s for s in sales if s.get("metodo_pago") == metodo_key]
    if producto_filter.strip():
        q = producto_filter.strip().lower()
        sales = [s for s in sales if q in (s.get("producto") or "").lower()]

    # ── Totales consolidados ───────────────────────────────────────────────── #
    st.divider()
    pago_totals: dict[str, Decimal] = {k: Decimal("0") for k in _METODOS_KEYS}
    total_gral = Decimal("0")
    total_cantidad = Decimal("0")

    for s in sales:
        total_gral += Decimal(str(s["precio_total"] or 0))
        total_cantidad += Decimal(str(s["cantidad"] or 0))
        mp = s.get("metodo_pago")
        if mp in pago_totals:
            pago_totals[mp] += Decimal(str(s["precio_total"] or 0))

    st.subheader("💰 Totales")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total general", _fmt(total_gral))
    c2.metric("N° de ventas", len(sales))
    c3.metric("Cantidad total productos", f"{float(total_cantidad):g}")

    p1, p2, p3, p4 = st.columns(4)
    p1.metric("💵 Efectivo", _fmt(pago_totals[db.METODO_EFECTIVO]))
    p2.metric("📱 Yape", _fmt(pago_totals[db.METODO_YAPE]))
    p3.metric("📲 Plin", _fmt(pago_totals[db.METODO_PLIN]))
    p4.metric("🏦 Transferencia", _fmt(pago_totals[db.METODO_TRANSFERENCIA]))

    # ── Gráfico métodos de pago ────────────────────────────────────────────── #
    metodo_data = {
        _METODOS_LABEL[k]: float(v)
        for k, v in pago_totals.items()
        if v > 0
    }
    if metodo_data:
        st.divider()
        st.subheader("📊 Distribución por método de pago")
        df_bar = pd.DataFrame.from_dict(metodo_data, orient="index",
                                         columns=["Monto"])
        st.bar_chart(df_bar)

    # ── Tabla detallada ───────────────────────────────────────────────────── #
    st.divider()
    st.subheader("📋 Detalle de ventas")
    if not sales:
        st.info("No se encontraron ventas con los filtros seleccionados.")
        return

    rows = [
        {
            "N° Venta": s["id"],
            "Fecha": str(s["created_at"])[:10],
            "Hora": str(s["created_at"])[11:16],
            "Usuario": s["usuario_rol"] or "—",
            "Sede": s["sede"],
            "Producto": s["producto"],
            "Cantidad": float(s["cantidad"]),
            "Unidad": s["unidad"],
            "P. Unit.": _money(s["precio_unitario"]),
            "Total": _money(s["precio_total"]),
            "Método pago": _METODOS_LABEL.get(s.get("metodo_pago"),
                                               s.get("metodo_pago") or "—"),
        }
        for s in sales
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.caption(f"**{len(rows)}** registros · Total: **{_fmt(total_gral)}**")
