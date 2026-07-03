"""Sales report view for ECOMAJES ERP.

Sales are derived automatically from ``venta`` inventory movements (recorded
with date, user, product, quantity, unit price, total price and location). This
view lets the administrative user filter by period (day / week / month / year)
and location (Sede Principal / Sucursal / Empresa Completa), see the key totals,
and record optional daily observations and expenses. Expenses feed the shared
``db.financial_summary`` helper that Balance Financiero will reuse later.
"""

import calendar
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

import streamlit as st

from ecomajes import config, db

_EMPRESA_COMPLETA = config.SEDE_EMPRESA_COMPLETA
_LOCATIONS = [config.SEDE_PRINCIPAL, config.SEDE_SUCURSAL, _EMPRESA_COMPLETA]
_EXPENSE_LOCATIONS = [config.SEDE_PRINCIPAL, config.SEDE_SUCURSAL]
_PERIODS = ["Día", "Semana", "Mes", "Año"]


def _period_range(period: str, ref: date) -> tuple[date, date]:
    """Return the (from, to) date range for a period around a reference date."""
    if period == "Semana":
        start = ref - timedelta(days=ref.weekday())
        return start, start + timedelta(days=6)
    if period == "Mes":
        last = calendar.monthrange(ref.year, ref.month)[1]
        return ref.replace(day=1), ref.replace(day=last)
    if period == "Año":
        return date(ref.year, 1, 1), date(ref.year, 12, 31)
    return ref, ref  # Día


def _money(value) -> float:
    return float(value) if value is not None else 0.0


def _summary_section(sede, include_all, date_from, date_to) -> None:
    summary = db.financial_summary(
        sede=sede,
        include_all_sedes=include_all,
        date_from=date_from,
        date_to=date_to,
    )
    c1, c2, c3 = st.columns(3)
    c1.metric("Total de ventas", summary["total_sales"])
    c2.metric("Productos vendidos", f"{float(summary['total_products']):g}")
    c3.metric("Ingresos totales", f"$ {_money(summary['total_revenue']):,.2f}")
    c4, c5 = st.columns(2)
    c4.metric("Gastos totales", f"$ {_money(summary['total_expenses']):,.2f}")
    c5.metric("Utilidad neta", f"$ {_money(summary['net_income']):,.2f}")


def _sales_table(sede, include_all, date_from, date_to) -> None:
    st.subheader("Ventas del periodo")
    sales = db.list_sales(
        sede=sede,
        include_all_sedes=include_all,
        date_from=date_from,
        date_to=date_to,
    )
    if not sales:
        st.caption("No hay ventas registradas en este periodo.")
        return
    rows = [
        {
            "Fecha": s["created_at"].strftime("%Y-%m-%d %H:%M"),
            "Usuario": s["usuario_rol"] or "—",
            "Producto": s["producto"],
            "Cantidad": float(s["cantidad"]),
            "Unidad": s["unidad"],
            "Precio unit.": _money(s["precio_unitario"]),
            "Precio total": _money(s["precio_total"]),
            "Ubicación": s["sede"],
        }
        for s in sales
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _expenses_section(ctx, sede, include_all, date_from, date_to, ref) -> None:
    st.subheader("Gastos del periodo")
    expenses = db.list_expenses(
        sede=sede,
        include_all_sedes=include_all,
        date_from=date_from,
        date_to=date_to,
    )
    if expenses:
        rows = [
            {
                "Fecha": e["fecha"].strftime("%Y-%m-%d"),
                "Descripción": e["descripcion"],
                "Monto": _money(e["monto"]),
                "Ubicación": e["sede"],
                "Usuario": e["usuario_rol"] or "—",
            }
            for e in expenses
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.caption("No hay gastos registrados en este periodo.")

    if not ctx["editable"]:
        return
    with st.expander("➕ Registrar gasto"):
        with st.form("add_expense_form", clear_on_submit=True):
            descripcion = st.text_input("Descripción")
            col1, col2 = st.columns(2)
            with col1:
                monto = st.number_input("Monto", min_value=0.0, value=0.0, step=1.0)
            with col2:
                fecha = st.date_input("Fecha", value=ref, key="expense_date")
            ubicacion = st.selectbox("Ubicación", _EXPENSE_LOCATIONS)
            submitted = st.form_submit_button("Guardar gasto")
        if submitted:
            if not descripcion.strip():
                st.error("La descripción del gasto es obligatoria.")
            elif monto <= 0:
                st.error("El monto debe ser mayor que cero.")
            else:
                try:
                    db.add_expense(
                        fecha=fecha,
                        descripcion=descripcion.strip(),
                        monto=Decimal(str(monto)),
                        sede=ubicacion,
                        usuario_rol=ctx["usuario_rol"],
                    )
                except (InvalidOperation, Exception) as exc:  # noqa: BLE001
                    st.error(f"No se pudo guardar el gasto: {exc}")
                else:
                    st.success("Gasto registrado.")
                    st.rerun()


def _observations_section(ctx, sede, include_all, date_from, date_to, ref) -> None:
    st.subheader("Observaciones del periodo")
    observations = db.list_observations(
        sede=sede,
        include_all_sedes=include_all,
        date_from=date_from,
        date_to=date_to,
    )
    if observations:
        for o in observations:
            st.markdown(
                f"**{o['fecha'].strftime('%Y-%m-%d')} · {o['sede']}** — "
                f"{o['observacion']}"
            )
    else:
        st.caption("No hay observaciones registradas en este periodo.")

    if not ctx["editable"]:
        return
    with st.expander("➕ Agregar observación"):
        with st.form("add_observation_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                fecha = st.date_input("Fecha", value=ref, key="obs_date")
            with col2:
                ubicacion = st.selectbox("Ubicación", _EXPENSE_LOCATIONS, key="obs_loc")
            texto = st.text_area("Observación")
            submitted = st.form_submit_button("Guardar observación")
        if submitted:
            if not texto.strip():
                st.error("La observación no puede estar vacía.")
            else:
                try:
                    db.add_observation(
                        fecha=fecha,
                        sede=ubicacion,
                        observacion=texto.strip(),
                        usuario_rol=ctx["usuario_rol"],
                    )
                except Exception as exc:  # noqa: BLE001
                    st.error(f"No se pudo guardar la observación: {exc}")
                else:
                    st.success("Observación registrada.")
                    st.rerun()


def render(ctx: dict) -> None:
    st.header(ctx["title"])
    st.caption(ctx["breadcrumb"])

    # --- Filters: period + reference date + location. --------------------- #
    col1, col2, col3 = st.columns(3)
    with col1:
        period = st.radio("Periodo", _PERIODS, horizontal=True)
    with col2:
        ref = st.date_input("Fecha de referencia", value=date.today())
    with col3:
        default_loc = ctx["sede"] if ctx["sede"] in _LOCATIONS else config.SEDE_PRINCIPAL
        ubicacion = st.selectbox(
            "Ubicación", _LOCATIONS, index=_LOCATIONS.index(default_loc)
        )

    date_from, date_to = _period_range(period, ref)
    include_all = ubicacion == _EMPRESA_COMPLETA
    sede = None if include_all else ubicacion

    st.caption(f"Periodo: {date_from} → {date_to} · Ubicación: {ubicacion}")
    st.divider()

    _summary_section(sede, include_all, date_from, date_to)
    st.divider()
    _sales_table(sede, include_all, date_from, date_to)
    st.divider()
    _expenses_section(ctx, sede, include_all, date_from, date_to, ref)
    st.divider()
    _observations_section(ctx, sede, include_all, date_from, date_to, ref)
