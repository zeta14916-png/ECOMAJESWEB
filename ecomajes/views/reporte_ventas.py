"""Sales report view for ECOMAJES ERP.

Sales are derived automatically from ``venta`` inventory movements. This view
lets the administrative user filter by period and location, see key totals
broken down by payment method, register caja chica (NOT counted as income),
additional income, debtors, envelope deliveries, observations and expenses,
and review a full-day summary at the bottom.
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


def _fmt(value) -> str:
    return f"S/ {_money(value):,.2f}"


# --------------------------------------------------------------------------- #
# Summary KPIs + sales table
# --------------------------------------------------------------------------- #
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
    c3.metric("Ingresos totales", _fmt(summary["total_revenue"]))
    c4, c5 = st.columns(2)
    c4.metric("Gastos totales", _fmt(summary["total_expenses"]))
    c5.metric("Utilidad neta", _fmt(summary["net_income"]))


def _sales_table(sede, include_all, date_from, date_to) -> None:
    st.subheader("📦 Ventas del periodo")
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
            "Método pago": (
                db.METODO_PAGO_LABELS.get(s.get("metodo_pago"), s.get("metodo_pago"))
                if s.get("metodo_pago")
                else "—"
            ),
            "Ubicación": s["sede"],
        }
        for s in sales
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)


# --------------------------------------------------------------------------- #
# Payment method breakdown
# --------------------------------------------------------------------------- #
def _metodo_pago_section(sede, include_all, date_from, date_to) -> None:
    st.subheader("💳 Métodos de pago")
    totals = db.sales_by_metodo_pago(
        sede=sede,
        include_all_sedes=include_all,
        date_from=date_from,
        date_to=date_to,
    )
    cols = st.columns(4)
    metodos = [
        (db.METODO_EFECTIVO, "💵 Efectivo"),
        (db.METODO_YAPE, "📱 Yape"),
        (db.METODO_PLIN, "📲 Plin"),
        (db.METODO_TRANSFERENCIA, "🏦 Transferencia"),
    ]
    for col, (key, label) in zip(cols, metodos):
        col.metric(label, _fmt(totals.get(key, Decimal("0"))))


# --------------------------------------------------------------------------- #
# Caja chica (NOT income — balance check only)
# --------------------------------------------------------------------------- #
def _caja_chica_section(ctx, sede, include_all, date_from, date_to, ref) -> None:
    st.subheader("🏦 Caja Chica")
    st.caption("La caja chica NO se considera ingreso. Es un arqueo de efectivo.")

    registros = db.list_caja_chica(
        sede=sede,
        include_all_sedes=include_all,
        date_from=date_from,
        date_to=date_to,
    )
    if registros:
        rows = [
            {
                "Fecha": r["fecha"].strftime("%Y-%m-%d"),
                "Sede": r["sede"],
                "Monto base": _money(r["monto_base"]),
                "Dinero contado": _money(r["dinero_contado"]),
                "Diferencia": _money(r["diferencia"]),
                "Observaciones": r["observaciones"] or "—",
                "Usuario": r["usuario_rol"] or "—",
            }
            for r in registros
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.caption("Sin registros de caja chica en este periodo.")

    if not ctx["editable"]:
        return
    with st.expander("➕ Registrar arqueo de Caja Chica"):
        with st.form("caja_chica_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                fecha = st.date_input("Fecha", value=ref, key="cc_fecha")
            with col2:
                ubicacion = st.selectbox("Sede", _EXPENSE_LOCATIONS, key="cc_sede")
            col3, col4 = st.columns(2)
            with col3:
                monto_base = st.number_input(
                    "Monto base", min_value=0.0, value=0.0, step=0.01, key="cc_base"
                )
            with col4:
                dinero_contado = st.number_input(
                    "Dinero contado", min_value=0.0, value=0.0, step=0.01, key="cc_contado"
                )
            observaciones = st.text_area("Observaciones (opcional)", key="cc_obs")
            submitted = st.form_submit_button("Guardar arqueo")
        if submitted:
            try:
                db.save_caja_chica(
                    fecha=fecha,
                    sede=ubicacion,
                    monto_base=Decimal(str(monto_base)),
                    dinero_contado=Decimal(str(dinero_contado)),
                    observaciones=observaciones.strip() or None,
                    usuario_rol=ctx["usuario_rol"],
                )
            except Exception as exc:
                st.error(f"No se pudo guardar: {exc}")
            else:
                diferencia = dinero_contado - monto_base
                st.success(
                    f"Arqueo guardado. Diferencia: {_fmt(Decimal(str(diferencia)))}"
                )
                st.rerun()


# --------------------------------------------------------------------------- #
# Additional income
# --------------------------------------------------------------------------- #
def _ingresos_adicionales_section(ctx, sede, include_all, date_from, date_to, ref) -> None:
    st.subheader("➕ Ingresos Adicionales")
    items = db.list_ingresos_adicionales(
        sede=sede,
        include_all_sedes=include_all,
        date_from=date_from,
        date_to=date_to,
    )
    if items:
        rows = [
            {
                "Fecha": i["fecha"].strftime("%Y-%m-%d"),
                "Sede": i["sede"],
                "Descripción": i["descripcion"],
                "Monto": _money(i["monto"]),
                "Usuario": i["usuario_rol"] or "—",
            }
            for i in items
        ]
        total_ia = sum(_money(i["monto"]) for i in items)
        st.dataframe(rows, use_container_width=True, hide_index=True)
        st.caption(f"Total ingresos adicionales: **{_fmt(Decimal(str(total_ia)))}**")
    else:
        st.caption("Sin ingresos adicionales en este periodo.")

    if not ctx["editable"]:
        return
    with st.expander("➕ Registrar ingreso adicional"):
        with st.form("ingreso_adicional_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                fecha = st.date_input("Fecha", value=ref, key="ia_fecha")
            with col2:
                ubicacion = st.selectbox("Sede", _EXPENSE_LOCATIONS, key="ia_sede")
            descripcion = st.text_input("Descripción")
            monto = st.number_input("Monto", min_value=0.0, value=0.0, step=0.01)
            submitted = st.form_submit_button("Guardar ingreso adicional")
        if submitted:
            if not descripcion.strip():
                st.error("La descripción es obligatoria.")
            elif monto <= 0:
                st.error("El monto debe ser mayor que cero.")
            else:
                try:
                    db.add_ingreso_adicional(
                        fecha=fecha,
                        sede=ubicacion,
                        descripcion=descripcion.strip(),
                        monto=Decimal(str(monto)),
                        usuario_rol=ctx["usuario_rol"],
                    )
                except Exception as exc:
                    st.error(f"No se pudo guardar: {exc}")
                else:
                    st.success("Ingreso adicional registrado.")
                    st.rerun()


# --------------------------------------------------------------------------- #
# Expenses
# --------------------------------------------------------------------------- #
def _expenses_section(ctx, sede, include_all, date_from, date_to, ref) -> None:
    st.subheader("📋 Gastos del periodo")
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
        total_exp = sum(_money(e["monto"]) for e in expenses)
        st.dataframe(rows, use_container_width=True, hide_index=True)
        st.caption(f"Total gastos: **{_fmt(Decimal(str(total_exp)))}**")
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
                    db.log_audit(
                        db.AUDIT_EXPENSE,
                        "Reporte de Ventas",
                        detalle=(
                            f"{descripcion.strip()} · "
                            f"S/ {float(monto):,.2f} · {ubicacion}"
                        ),
                        usuario_rol=ctx["usuario_rol"],
                        sede=ubicacion,
                    )
                    st.success("Gasto registrado.")
                    st.rerun()


# --------------------------------------------------------------------------- #
# Debtors
# --------------------------------------------------------------------------- #
def _deudores_section(ctx, sede, include_all, date_from, date_to, ref) -> None:
    st.subheader("👤 Deudores")
    items = db.list_deudores(
        sede=sede,
        include_all_sedes=include_all,
        date_from=date_from,
        date_to=date_to,
    )
    if items:
        rows = [
            {
                "Fecha": i["fecha"].strftime("%Y-%m-%d"),
                "Sede": i["sede"],
                "Nombre": i["nombre"],
                "Descripción": i["descripcion"] or "—",
                "Monto": _money(i["monto"]),
                "Usuario": i["usuario_rol"] or "—",
            }
            for i in items
        ]
        total_deu = sum(_money(i["monto"]) for i in items)
        st.dataframe(rows, use_container_width=True, hide_index=True)
        st.caption(f"Total deudores: **{_fmt(Decimal(str(total_deu)))}**")
    else:
        st.caption("Sin deudores registrados en este periodo.")

    if not ctx["editable"]:
        return
    with st.expander("➕ Registrar deudor"):
        with st.form("deudor_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                fecha = st.date_input("Fecha", value=ref, key="deu_fecha")
            with col2:
                ubicacion = st.selectbox("Sede", _EXPENSE_LOCATIONS, key="deu_sede")
            nombre = st.text_input("Nombre del deudor")
            descripcion = st.text_input("Descripción (opcional)", key="deu_desc")
            monto = st.number_input("Monto adeudado", min_value=0.0, value=0.0, step=0.01, key="deu_monto")
            submitted = st.form_submit_button("Registrar deudor")
        if submitted:
            if not nombre.strip():
                st.error("El nombre del deudor es obligatorio.")
            elif monto <= 0:
                st.error("El monto debe ser mayor que cero.")
            else:
                try:
                    db.add_deudor(
                        fecha=fecha,
                        sede=ubicacion,
                        nombre=nombre.strip(),
                        descripcion=descripcion.strip() or None,
                        monto=Decimal(str(monto)),
                        usuario_rol=ctx["usuario_rol"],
                    )
                except Exception as exc:
                    st.error(f"No se pudo guardar: {exc}")
                else:
                    st.success("Deudor registrado.")
                    st.rerun()


# --------------------------------------------------------------------------- #
# Entrega de sobres
# --------------------------------------------------------------------------- #
def _entrega_sobres_section(ctx, sede, include_all, date_from, date_to, ref) -> None:
    st.subheader("✉️ Entrega de Sobres")
    items = db.list_entregas_sobres(
        sede=sede,
        include_all_sedes=include_all,
        date_from=date_from,
        date_to=date_to,
    )
    if items:
        rows = [
            {
                "Fecha": i["fecha"].strftime("%Y-%m-%d"),
                "Sede": i["sede"],
                "Descripción": i["descripcion"],
                "Monto": _money(i["monto"]),
                "Usuario": i["usuario_rol"] or "—",
            }
            for i in items
        ]
        total_sob = sum(_money(i["monto"]) for i in items)
        st.dataframe(rows, use_container_width=True, hide_index=True)
        st.caption(f"Total entrega de sobres: **{_fmt(Decimal(str(total_sob)))}**")
    else:
        st.caption("Sin entregas de sobres en este periodo.")

    if not ctx["editable"]:
        return
    with st.expander("➕ Registrar entrega de sobre"):
        with st.form("entrega_sobre_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                fecha = st.date_input("Fecha", value=ref, key="esob_fecha")
            with col2:
                ubicacion = st.selectbox("Sede", _EXPENSE_LOCATIONS, key="esob_sede")
            descripcion = st.text_input("Descripción")
            monto = st.number_input("Monto", min_value=0.0, value=0.0, step=0.01, key="esob_monto")
            submitted = st.form_submit_button("Registrar entrega")
        if submitted:
            if not descripcion.strip():
                st.error("La descripción es obligatoria.")
            elif monto <= 0:
                st.error("El monto debe ser mayor que cero.")
            else:
                try:
                    db.add_entrega_sobre(
                        fecha=fecha,
                        sede=ubicacion,
                        descripcion=descripcion.strip(),
                        monto=Decimal(str(monto)),
                        usuario_rol=ctx["usuario_rol"],
                    )
                except Exception as exc:
                    st.error(f"No se pudo guardar: {exc}")
                else:
                    st.success("Entrega de sobre registrada.")
                    st.rerun()


# --------------------------------------------------------------------------- #
# Observations
# --------------------------------------------------------------------------- #
def _observations_section(ctx, sede, include_all, date_from, date_to, ref) -> None:
    st.subheader("📝 Observaciones del periodo")
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


# --------------------------------------------------------------------------- #
# Resumen final
# --------------------------------------------------------------------------- #
def _resumen_final(sede, include_all, date_from, date_to) -> None:
    st.subheader("📊 Resumen Final del Periodo")

    # Collect all data.
    summary = db.financial_summary(
        sede=sede,
        include_all_sedes=include_all,
        date_from=date_from,
        date_to=date_to,
    )
    pago_totals = db.sales_by_metodo_pago(
        sede=sede,
        include_all_sedes=include_all,
        date_from=date_from,
        date_to=date_to,
    )
    ingresos_add = db.list_ingresos_adicionales(
        sede=sede, include_all_sedes=include_all,
        date_from=date_from, date_to=date_to,
    )
    gastos_list = db.list_expenses(
        sede=sede, include_all_sedes=include_all,
        date_from=date_from, date_to=date_to,
    )
    cc_list = db.list_caja_chica(
        sede=sede, include_all_sedes=include_all,
        date_from=date_from, date_to=date_to,
    )
    entrega_list = db.list_entregas_sobres(
        sede=sede, include_all_sedes=include_all,
        date_from=date_from, date_to=date_to,
    )

    total_vendido = Decimal(str(summary["total_revenue"]))
    efec = pago_totals.get(db.METODO_EFECTIVO, Decimal("0"))
    yape = pago_totals.get(db.METODO_YAPE, Decimal("0"))
    plin = pago_totals.get(db.METODO_PLIN, Decimal("0"))
    transf = pago_totals.get(db.METODO_TRANSFERENCIA, Decimal("0"))
    total_ia = sum(Decimal(str(i["monto"])) for i in ingresos_add)
    total_gastos = sum(Decimal(str(g["monto"])) for g in gastos_list)
    # Caja chica: show monto_base and dinero_contado for reference only.
    cc_base = sum(Decimal(str(c["monto_base"])) for c in cc_list)
    cc_contado = sum(Decimal(str(c["dinero_contado"])) for c in cc_list)
    cc_diff = cc_contado - cc_base
    total_sobres = sum(Decimal(str(e["monto"])) for e in entrega_list)
    # Net = total_vendido + ia - gastos - sobres (caja chica NOT included)
    utilidad = total_vendido + total_ia - total_gastos - total_sobres

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Ingresos por ventas")
        st.metric("Total vendido", _fmt(total_vendido))
        st.metric("└ Efectivo", _fmt(efec))
        st.metric("└ Yape", _fmt(yape))
        st.metric("└ Plin", _fmt(plin))
        st.metric("└ Transferencia", _fmt(transf))
        st.metric("Ingresos adicionales", _fmt(total_ia))
    with col2:
        st.markdown("#### Egresos y otros")
        st.metric("Gastos", _fmt(total_gastos))
        st.metric("Entrega de sobres", _fmt(total_sobres))
        st.metric("Caja chica (base)", _fmt(cc_base))
        st.metric("Caja chica (contado)", _fmt(cc_contado))
        st.metric("Diferencia caja chica", _fmt(cc_diff))

    st.divider()
    utilidad_color = "normal" if utilidad >= 0 else "inverse"
    st.metric(
        "💰 Diferencia neta del periodo",
        _fmt(utilidad),
        help="Total vendido + Ingresos adicionales − Gastos − Entrega de sobres. "
             "La caja chica NO se suma.",
        delta_color=utilidad_color,
    )


# --------------------------------------------------------------------------- #
# Main render
# --------------------------------------------------------------------------- #
def render(ctx: dict) -> None:
    st.header(ctx["title"])
    st.caption(ctx["breadcrumb"])

    # Filters: period + reference date + location.
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
    _metodo_pago_section(sede, include_all, date_from, date_to)
    st.divider()
    _sales_table(sede, include_all, date_from, date_to)
    st.divider()
    _caja_chica_section(ctx, sede, include_all, date_from, date_to, ref)
    st.divider()
    _ingresos_adicionales_section(ctx, sede, include_all, date_from, date_to, ref)
    st.divider()
    _expenses_section(ctx, sede, include_all, date_from, date_to, ref)
    st.divider()
    _deudores_section(ctx, sede, include_all, date_from, date_to, ref)
    st.divider()
    _entrega_sobres_section(ctx, sede, include_all, date_from, date_to, ref)
    st.divider()
    _observations_section(ctx, sede, include_all, date_from, date_to, ref)
    st.divider()
    _resumen_final(sede, include_all, date_from, date_to)
