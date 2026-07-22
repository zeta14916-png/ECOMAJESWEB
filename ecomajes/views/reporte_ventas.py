"""Sales report view for ECOMAJES ERP — FASE 2.

Includes:
- Payment method breakdown (Efectivo, Yape, Plin, Transferencia, Caja Chica)
- Ingresos adicionales
- Gastos
- Deudores
- Entrega de sobres
- Observaciones
- Resumen completo

Sales are derived from ``venta`` inventory movements. The view lets the
administrative user filter by period and location, see key totals and enter
optional daily entries (expenses, additional income, debtors, envelope deliveries).
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


# --------------------------------------------------------------------------- #
# Tab 1: Ventas
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
            "Método de pago": db.METODO_PAGO_LABELS.get(s.get("metodo_pago") or "", s.get("metodo_pago") or "Efectivo"),
            "Precio unit.": _money(s["precio_unitario"]),
            "Precio total": _money(s["precio_total"]),
            "Tipo venta": db.TIPO_VENTA_LABELS.get(s.get("tipo_venta") or "", "—"),
            "Ubicación": s["sede"],
        }
        for s in sales
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)


# --------------------------------------------------------------------------- #
# Tab 2: Pagos (métodos de pago)
# --------------------------------------------------------------------------- #

def _payment_breakdown_section(sede, include_all, date_from, date_to) -> None:
    st.subheader("💳 Desglose por método de pago")

    totals = db.sales_by_metodo_pago(
        sede=sede,
        include_all_sedes=include_all,
        date_from=date_from,
        date_to=date_to,
    )

    # Build a dict metodo_pago -> total
    totals_map = {r["metodo_pago"]: r for r in totals}
    grand_total = sum(_money(r["total"]) for r in totals)

    cols = st.columns(len(db.METODOS_PAGO))
    for i, metodo in enumerate(db.METODOS_PAGO):
        row = totals_map.get(metodo)
        monto = _money(row["total"]) if row else 0.0
        num = int(row["num_ventas"]) if row else 0
        cols[i].metric(
            db.METODO_PAGO_LABELS[metodo],
            f"$ {monto:,.2f}",
            delta=f"{num} venta{'s' if num != 1 else ''}",
            delta_color="off",
        )

    st.divider()
    if totals:
        rows = [
            {
                "Método de pago": db.METODO_PAGO_LABELS.get(r["metodo_pago"], r["metodo_pago"]),
                "N° ventas": int(r["num_ventas"]),
                "Total recaudado": _money(r["total"]),
                "% del total": f"{(_money(r['total']) / grand_total * 100):.1f}%" if grand_total > 0 else "0.0%",
            }
            for r in totals
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)
        st.caption(f"**Total general recaudado:** $ {grand_total:,.2f}")
    else:
        st.caption("No hay ventas registradas en este periodo.")


# --------------------------------------------------------------------------- #
# Tab 3: Ingresos adicionales + Gastos
# --------------------------------------------------------------------------- #

def _ingresos_adicionales_section(ctx, sede, include_all, date_from, date_to, ref) -> None:
    st.subheader("➕ Ingresos adicionales")
    ingresos = db.list_ingresos_adicionales(
        sede=sede,
        include_all_sedes=include_all,
        date_from=date_from,
        date_to=date_to,
    )
    total_adicional = sum(_money(i["monto"]) for i in ingresos)
    if ingresos:
        rows = [
            {
                "Fecha": i["fecha"].strftime("%Y-%m-%d"),
                "Descripción": i["descripcion"],
                "Monto": _money(i["monto"]),
                "Ubicación": i["sede"],
                "Usuario": i["usuario_rol"] or "—",
            }
            for i in ingresos
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)
        st.caption(f"**Total ingresos adicionales:** $ {total_adicional:,.2f}")
    else:
        st.caption("No hay ingresos adicionales registrados en este periodo.")

    if not ctx["editable"]:
        return
    with st.expander("➕ Registrar ingreso adicional"):
        with st.form("add_ingreso_form", clear_on_submit=True):
            descripcion = st.text_input("Descripción del ingreso")
            col1, col2 = st.columns(2)
            with col1:
                monto = st.number_input("Monto", min_value=0.0, value=0.0, step=1.0)
            with col2:
                fecha = st.date_input("Fecha", value=ref, key="ingreso_date")
            ubicacion = st.selectbox("Ubicación", _EXPENSE_LOCATIONS, key="ingreso_loc")
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
                        descripcion=descripcion.strip(),
                        monto=Decimal(str(monto)),
                        sede=ubicacion,
                        usuario_rol=ctx["usuario_rol"],
                    )
                except Exception as exc:  # noqa: BLE001
                    st.error(f"No se pudo guardar: {exc}")
                else:
                    st.success("Ingreso adicional registrado.")
                    st.rerun()


def _expenses_section(ctx, sede, include_all, date_from, date_to, ref) -> None:
    st.subheader("💸 Gastos del periodo")
    expenses = db.list_expenses(
        sede=sede,
        include_all_sedes=include_all,
        date_from=date_from,
        date_to=date_to,
    )
    total_gastos = sum(_money(e["monto"]) for e in expenses)
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
        st.caption(f"**Total gastos:** $ {total_gastos:,.2f}")
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
                            f"$ {float(monto):,.2f} · {ubicacion}"
                        ),
                        usuario_rol=ctx["usuario_rol"],
                        sede=ubicacion,
                    )
                    st.success("Gasto registrado.")
                    st.rerun()


# --------------------------------------------------------------------------- #
# Tab 4: Deudores + Entrega de sobres
# --------------------------------------------------------------------------- #

def _deudores_section(ctx, sede, include_all) -> None:
    st.subheader("🧾 Deudores")
    col_f, col_f2 = st.columns(2)
    with col_f:
        filtro_estado = st.selectbox(
            "Filtrar por estado",
            ["Todos", db.DEUDOR_PENDIENTE, db.DEUDOR_PAGADO],
            format_func=lambda e: "Todos" if e == "Todos" else db.DEUDOR_STATUS_LABELS.get(e, e),
            key="deudores_filtro_estado",
        )
    estado_q = None if filtro_estado == "Todos" else filtro_estado
    deudores = db.list_deudores(
        sede=sede,
        include_all_sedes=include_all,
        estado=estado_q,
    )
    total_pendiente = sum(
        _money(d["monto"]) for d in deudores if d["estado"] == db.DEUDOR_PENDIENTE
    )
    if deudores:
        rows = [
            {
                "Nombre": d["nombre"],
                "Descripción": d["descripcion"],
                "Monto": _money(d["monto"]),
                "Estado": db.DEUDOR_STATUS_LABELS.get(d["estado"], d["estado"]),
                "Ubicación": d["sede"],
                "Usuario": d["usuario_rol"] or "—",
                "Fecha": d["created_at"].strftime("%Y-%m-%d"),
            }
            for d in deudores
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)
        st.caption(f"**Total deudas pendientes:** $ {total_pendiente:,.2f}")

        # Allow marking individual deudores as pagado
        if ctx["editable"] and deudores:
            with st.expander("✅ Marcar deudor como pagado"):
                pendientes = [d for d in deudores if d["estado"] == db.DEUDOR_PENDIENTE]
                if not pendientes:
                    st.caption("No hay deudores pendientes.")
                else:
                    deudor_id = st.selectbox(
                        "Seleccionar deudor",
                        [d["id"] for d in pendientes],
                        format_func=lambda did: next(
                            f"{d['nombre']} — $ {_money(d['monto']):,.2f}"
                            for d in pendientes if d["id"] == did
                        ),
                        key="deudor_sel",
                    )
                    if st.button("Marcar como pagado", key="deudor_pagar"):
                        try:
                            db.set_deudor_estado(deudor_id, db.DEUDOR_PAGADO)
                        except Exception as exc:  # noqa: BLE001
                            st.error(f"Error: {exc}")
                        else:
                            st.success("Deudor marcado como pagado.")
                            st.rerun()
    else:
        st.caption("No hay deudores registrados.")

    if not ctx["editable"]:
        return
    with st.expander("➕ Registrar deudor"):
        with st.form("add_deudor_form", clear_on_submit=True):
            nombre = st.text_input("Nombre del deudor")
            descripcion = st.text_input("Descripción / concepto")
            col1, col2 = st.columns(2)
            with col1:
                monto = st.number_input("Monto adeudado", min_value=0.0, value=0.0, step=1.0)
            with col2:
                ubicacion = st.selectbox("Sede", _EXPENSE_LOCATIONS, key="deudor_sede")
            submitted = st.form_submit_button("Registrar deudor")
        if submitted:
            if not nombre.strip():
                st.error("El nombre del deudor es obligatorio.")
            elif monto <= 0:
                st.error("El monto debe ser mayor que cero.")
            else:
                try:
                    db.add_deudor(
                        nombre=nombre.strip(),
                        descripcion=descripcion.strip(),
                        monto=Decimal(str(monto)),
                        sede=ubicacion,
                        usuario_rol=ctx["usuario_rol"],
                    )
                except Exception as exc:  # noqa: BLE001
                    st.error(f"No se pudo registrar: {exc}")
                else:
                    st.success("Deudor registrado.")
                    st.rerun()


def _entrega_sobres_section(ctx, sede, include_all, date_from, date_to, ref) -> None:
    st.subheader("📬 Entrega de sobres")
    sobres = db.list_entrega_sobres(
        sede=sede,
        include_all_sedes=include_all,
        date_from=date_from,
        date_to=date_to,
    )
    total_sobres = sum(_money(s["monto"]) for s in sobres)
    if sobres:
        rows = [
            {
                "Fecha": s["fecha"].strftime("%Y-%m-%d"),
                "Destinatario": s["destinatario"],
                "Descripción": s["descripcion"],
                "Monto": _money(s["monto"]),
                "Ubicación": s["sede"],
                "Usuario": s["usuario_rol"] or "—",
            }
            for s in sobres
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)
        st.caption(f"**Total entregado en sobres:** $ {total_sobres:,.2f}")
    else:
        st.caption("No hay registros de entrega de sobres en este periodo.")

    if not ctx["editable"]:
        return
    with st.expander("➕ Registrar entrega de sobre"):
        with st.form("add_sobre_form", clear_on_submit=True):
            destinatario = st.text_input("Destinatario")
            descripcion = st.text_input("Descripción / concepto")
            col1, col2 = st.columns(2)
            with col1:
                monto = st.number_input("Monto", min_value=0.0, value=0.0, step=1.0)
            with col2:
                fecha_sobre = st.date_input("Fecha", value=ref, key="sobre_date")
            ubicacion = st.selectbox("Sede", _EXPENSE_LOCATIONS, key="sobre_sede")
            submitted = st.form_submit_button("Registrar entrega de sobre")
        if submitted:
            if not destinatario.strip():
                st.error("El destinatario es obligatorio.")
            elif monto <= 0:
                st.error("El monto debe ser mayor que cero.")
            else:
                try:
                    db.add_entrega_sobre(
                        fecha=fecha_sobre,
                        destinatario=destinatario.strip(),
                        descripcion=descripcion.strip(),
                        monto=Decimal(str(monto)),
                        sede=ubicacion,
                        usuario_rol=ctx["usuario_rol"],
                    )
                except Exception as exc:  # noqa: BLE001
                    st.error(f"No se pudo registrar: {exc}")
                else:
                    st.success("Entrega de sobre registrada.")
                    st.rerun()


# --------------------------------------------------------------------------- #
# Tab 5: Resumen
# --------------------------------------------------------------------------- #

def _resumen_section(sede, include_all, date_from, date_to) -> None:
    st.subheader("📈 Resumen del periodo")

    summary = db.financial_summary(
        sede=sede,
        include_all_sedes=include_all,
        date_from=date_from,
        date_to=date_to,
    )
    ingresos_ad = db.list_ingresos_adicionales(
        sede=sede, include_all_sedes=include_all,
        date_from=date_from, date_to=date_to,
    )
    deudores = db.list_deudores(
        sede=sede, include_all_sedes=include_all,
        estado=db.DEUDOR_PENDIENTE,
    )
    sobres = db.list_entrega_sobres(
        sede=sede, include_all_sedes=include_all,
        date_from=date_from, date_to=date_to,
    )
    totales_pago = db.sales_by_metodo_pago(
        sede=sede, include_all_sedes=include_all,
        date_from=date_from, date_to=date_to,
    )

    total_ventas = _money(summary["total_revenue"])
    total_adicionales = sum(_money(i["monto"]) for i in ingresos_ad)
    total_gastos = _money(summary["total_expenses"])
    total_deudas = sum(_money(d["monto"]) for d in deudores)
    total_sobres = sum(_money(s["monto"]) for s in sobres)
    total_ingresos = total_ventas + total_adicionales
    utilidad = total_ingresos - total_gastos - total_sobres

    st.markdown("#### 💰 Flujo de caja")
    col1, col2, col3 = st.columns(3)
    col1.metric("Ventas del periodo", f"$ {total_ventas:,.2f}")
    col2.metric("Ingresos adicionales", f"$ {total_adicionales:,.2f}")
    col3.metric("Total ingresos", f"$ {total_ingresos:,.2f}")

    col4, col5, col6 = st.columns(3)
    col4.metric("Gastos", f"$ {total_gastos:,.2f}")
    col5.metric("Entrega de sobres", f"$ {total_sobres:,.2f}")
    col6.metric(
        "Utilidad neta",
        f"$ {utilidad:,.2f}",
        delta=f"{'+' if utilidad >= 0 else ''}{utilidad:,.2f}",
        delta_color="normal",
    )

    st.divider()
    st.markdown("#### 💳 Recaudado por método de pago")
    if totales_pago:
        pay_rows = [
            {
                "Método": db.METODO_PAGO_LABELS.get(r["metodo_pago"], r["metodo_pago"]),
                "Ventas": int(r["num_ventas"]),
                "Total": f"$ {_money(r['total']):,.2f}",
            }
            for r in totales_pago
        ]
        st.dataframe(pay_rows, use_container_width=True, hide_index=True)
    else:
        st.caption("Sin ventas en el periodo.")

    if total_deudas > 0:
        st.divider()
        st.markdown(f"#### 🧾 Deudores pendientes: $ {total_deudas:,.2f}")
        st.caption(f"{len(deudores)} deudor(es) pendiente(s) de cobro.")


# --------------------------------------------------------------------------- #
# Observations (shared)
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
# Main render
# --------------------------------------------------------------------------- #

def render(ctx: dict) -> None:
    st.header(ctx["title"])
    st.caption(ctx["breadcrumb"])

    # --- Filters ------------------------------------------------------------ #
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

    st.caption(f"Periodo: **{date_from}** → **{date_to}** · Ubicación: **{ubicacion}**")
    st.divider()

    # --- Tabs --------------------------------------------------------------- #
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Ventas",
        "💳 Pagos",
        "➕ Ingresos y Gastos",
        "📋 Deudores y Sobres",
        "📈 Resumen",
    ])

    with tab1:
        _summary_section(sede, include_all, date_from, date_to)
        st.divider()
        _sales_table(sede, include_all, date_from, date_to)
        st.divider()
        _observations_section(ctx, sede, include_all, date_from, date_to, ref)

    with tab2:
        _payment_breakdown_section(sede, include_all, date_from, date_to)

    with tab3:
        _ingresos_adicionales_section(ctx, sede, include_all, date_from, date_to, ref)
        st.divider()
        _expenses_section(ctx, sede, include_all, date_from, date_to, ref)

    with tab4:
        _deudores_section(ctx, sede, include_all)
        st.divider()
        _entrega_sobres_section(ctx, sede, include_all, date_from, date_to, ref)

    with tab5:
        _resumen_section(sede, include_all, date_from, date_to)
