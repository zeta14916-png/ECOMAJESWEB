"""Sales report view for ECOMAJES ERP.

Sales are derived automatically from ``venta`` inventory movements. This view
lets the administrative user filter by period and location, see key totals
broken down by payment method, register caja chica (NOT counted as income),
additional income, debtors, envelope deliveries, observations and expenses,
and review a full-day summary at the bottom.
"""

import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

import streamlit as st

from ecomajes import config, db

_EMPRESA_COMPLETA = config.SEDE_EMPRESA_COMPLETA
_LOCATIONS = [config.SEDE_PRINCIPAL, config.SEDE_SUCURSAL, _EMPRESA_COMPLETA]
_EXPENSE_LOCATIONS = [config.SEDE_PRINCIPAL, config.SEDE_SUCURSAL]
_PERIODS = ["Día", "Semana", "Mes", "Año"]

# Métodos de ingreso adicional
_METODOS_INGRESO = ["Efectivo", "Yape", "Plin", "Transferencia"]
_METODO_KEY = {
    "Efectivo": "efectivo",
    "Yape": "yape",
    "Plin": "plin",
    "Transferencia": "transferencia",
}


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
def _estado_caja(diferencia: float) -> tuple[str, str]:
    """Retorna (estado_label, color_css) según la diferencia."""
    if diferencia == 0:
        return "✅ Caja correcta", "#2E7D32"
    if diferencia > 0:
        return f"⬆️ Sobrante: {_fmt(Decimal(str(diferencia)))}", "#1565C0"
    return f"⬇️ Faltante: {_fmt(Decimal(str(abs(diferencia))))}", "#D32F2F"


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
        rows = []
        for r in registros:
            diff = _money(r["diferencia"])
            estado_label, _ = _estado_caja(diff)
            rows.append(
                {
                    "Fecha": r["fecha"].strftime("%Y-%m-%d"),
                    "Sede": r["sede"],
                    "Monto base": _money(r["monto_base"]),
                    "Dinero contado": _money(r["dinero_contado"]),
                    "Diferencia": diff,
                    "Estado": estado_label,
                    "Sobrante": max(diff, 0.0),
                    "Faltante": max(-diff, 0.0),
                    "Justificación": r.get("justificacion") or r.get("observaciones") or "—",
                    "Usuario": r["usuario_rol"] or "—",
                }
            )
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
                    "Monto base (S/)", min_value=0.0, value=0.0, step=0.01, key="cc_base",
                    help="Monto fijo asignado a la caja chica.",
                )
            with col4:
                dinero_contado = st.number_input(
                    "Dinero contado (S/)", min_value=0.0, value=0.0, step=0.01, key="cc_contado",
                    help="Dinero físico contado al momento del arqueo.",
                )
            # Vista previa del estado
            diferencia_preview = dinero_contado - monto_base
            if diferencia_preview < 0:
                st.error(f"⚠️ Faltante: {_fmt(Decimal(str(abs(diferencia_preview))))} — Se requiere justificación.")
            elif diferencia_preview > 0:
                st.info(f"ℹ️ Sobrante: {_fmt(Decimal(str(diferencia_preview)))}")
            else:
                st.success("✅ Caja correcta")

            justificacion = st.text_area(
                "Justificación" + (" (obligatoria para faltante)" if diferencia_preview < 0 else " (opcional)"),
                placeholder="Indica el motivo de la diferencia encontrada…",
                key="cc_justif",
            )
            submitted = st.form_submit_button("Guardar arqueo")

        if submitted:
            diferencia = Decimal(str(dinero_contado)) - Decimal(str(monto_base))
            if diferencia < 0 and not justificacion.strip():
                st.error("❌ Cuando hay faltante, la justificación es obligatoria.")
            else:
                try:
                    db.save_caja_chica(
                        fecha=fecha,
                        sede=ubicacion,
                        monto_base=Decimal(str(monto_base)),
                        dinero_contado=Decimal(str(dinero_contado)),
                        observaciones=None,
                        usuario_rol=ctx["usuario_rol"],
                        justificacion=justificacion.strip() or None,
                    )
                except Exception as exc:
                    st.error(f"No se pudo guardar: {exc}")
                else:
                    estado_lbl, _ = _estado_caja(float(diferencia))
                    st.success(f"Arqueo guardado. {estado_lbl}")
                    st.rerun()


# --------------------------------------------------------------------------- #
# Additional income — con método de ingreso
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
                "Hora": str(i.get("hora") or "—")[:5],
                "Sede": i["sede"],
                "Descripción": i["descripcion"],
                "Método": (i.get("metodo_ingreso") or "efectivo").capitalize(),
                "Monto": _money(i["monto"]),
                "Usuario": i["usuario_rol"] or "—",
                "Observación": i.get("observacion") or "—",
            }
            for i in items
        ]
        total_ia = sum(_money(i["monto"]) for i in items)
        st.dataframe(rows, use_container_width=True, hide_index=True)
        st.caption(f"Total ingresos adicionales: **{_fmt(Decimal(str(total_ia)))}**")

        # Desglose por método
        st.markdown("**Desglose por método:**")
        metodos_disp = [
            ("efectivo", "💵 Efectivo"),
            ("yape", "📱 Yape"),
            ("plin", "📲 Plin"),
            ("transferencia", "🏦 Transferencia"),
        ]
        cols = st.columns(4)
        for col, (key, label) in zip(cols, metodos_disp):
            total_m = sum(
                _money(i["monto"])
                for i in items
                if (i.get("metodo_ingreso") or "efectivo").lower() == key
            )
            col.metric(label, _fmt(Decimal(str(total_m))))
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
            descripcion = st.text_input(
                "Descripción *",
                placeholder="Ej: Servicio de corte, alquiler de maquinaria…",
            )
            col3, col4 = st.columns(2)
            with col3:
                monto = st.number_input("Monto *", min_value=0.0, value=0.0, step=0.01)
            with col4:
                metodo_sel = st.selectbox(
                    "Método de ingreso *",
                    _METODOS_INGRESO,
                    help="Método con el que se recibió el pago.",
                )
            observacion = st.text_area(
                "Observación (opcional)",
                placeholder="Detalle adicional si es necesario…",
                key="ia_obs",
            )
            submitted = st.form_submit_button("Guardar ingreso adicional")

        if submitted:
            if not descripcion.strip():
                st.error("La descripción es obligatoria.")
            elif monto <= 0:
                st.error("El monto debe ser mayor que cero.")
            else:
                now = datetime.now()
                try:
                    db.add_ingreso_adicional(
                        fecha=fecha,
                        sede=ubicacion,
                        descripcion=descripcion.strip(),
                        monto=Decimal(str(monto)),
                        usuario_rol=ctx["usuario_rol"],
                        metodo_ingreso=_METODO_KEY.get(metodo_sel, metodo_sel.lower()),
                        hora=now.time(),
                        observacion=observacion.strip() or None,
                    )
                except Exception as exc:
                    st.error(f"No se pudo guardar: {exc}")
                else:
                    st.success(f"Ingreso adicional registrado ({metodo_sel}).")
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
# Resumen final — secciones organizadas con tarjetas
# --------------------------------------------------------------------------- #
def _card(label: str, value: str, color: str = "#1565C0") -> str:
    return (
        f"<div style='background:#fff;border-radius:10px;padding:0.8rem 1rem;"
        f"border-left:4px solid {color};box-shadow:0 1px 4px rgba(0,0,0,0.07);"
        f"margin-bottom:0.5rem;'>"
        f"<div style='font-size:0.78rem;color:#546E7A;font-weight:600;"
        f"text-transform:uppercase;letter-spacing:0.04em;'>{label}</div>"
        f"<div style='font-size:1.2rem;font-weight:800;color:#0047A1;'>{value}</div>"
        f"</div>"
    )


def _section_header(title: str) -> None:
    st.markdown(
        f"<div style='background:linear-gradient(90deg,#0047A1,#1565C0);"
        f"color:#fff;border-radius:8px;padding:0.5rem 1rem;margin:1rem 0 0.5rem;"
        f"font-weight:700;font-size:1rem;'>{title}</div>",
        unsafe_allow_html=True,
    )


def _resumen_final(sede, include_all, date_from, date_to) -> None:
    st.subheader("📊 Resumen Final del Periodo")

    # Recopilar todos los datos.
    summary = db.financial_summary(
        sede=sede, include_all_sedes=include_all,
        date_from=date_from, date_to=date_to,
    )
    pago_totals = db.sales_by_metodo_pago(
        sede=sede, include_all_sedes=include_all,
        date_from=date_from, date_to=date_to,
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

    # Cálculos base
    total_vendido = Decimal(str(summary["total_revenue"]))
    efec_v = pago_totals.get(db.METODO_EFECTIVO, Decimal("0"))
    yape_v = pago_totals.get(db.METODO_YAPE, Decimal("0"))
    plin_v = pago_totals.get(db.METODO_PLIN, Decimal("0"))
    transf_v = pago_totals.get(db.METODO_TRANSFERENCIA, Decimal("0"))

    total_ia = sum(Decimal(str(i["monto"])) for i in ingresos_add)
    ia_efec = sum(Decimal(str(i["monto"])) for i in ingresos_add
                  if (i.get("metodo_ingreso") or "efectivo").lower() == "efectivo")
    ia_yape = sum(Decimal(str(i["monto"])) for i in ingresos_add
                  if (i.get("metodo_ingreso") or "").lower() == "yape")
    ia_plin = sum(Decimal(str(i["monto"])) for i in ingresos_add
                  if (i.get("metodo_ingreso") or "").lower() == "plin")
    ia_transf = sum(Decimal(str(i["monto"])) for i in ingresos_add
                    if (i.get("metodo_ingreso") or "").lower() == "transferencia")

    total_gastos = sum(Decimal(str(g["monto"])) for g in gastos_list)
    total_sobres = sum(Decimal(str(e["monto"])) for e in entrega_list)

    # Caja chica: separar sobrante y faltante, NO sumar como ingreso
    cc_base = sum(Decimal(str(c["monto_base"])) for c in cc_list)
    cc_contado = sum(Decimal(str(c["dinero_contado"])) for c in cc_list)
    cc_diff = cc_contado - cc_base
    cc_sobrante = cc_diff if cc_diff > 0 else Decimal("0")
    cc_faltante = abs(cc_diff) if cc_diff < 0 else Decimal("0")
    if cc_diff == 0:
        cc_estado = "✅ Caja correcta"
    elif cc_diff > 0:
        cc_estado = "⬆️ Sobrante"
    else:
        cc_estado = "⬇️ Faltante"

    # Neto: ventas + IA - gastos - sobres (Caja Chica NO incluida)
    utilidad = total_vendido + total_ia - total_gastos - total_sobres

    col_a, col_b = st.columns(2)

    # ── A. VENTAS ────────────────────────────────────────────
    with col_a:
        _section_header("A. Ventas")
        st.markdown(
            _card("Total vendido", _fmt(total_vendido), "#0047A1") +
            _card("└ Efectivo", _fmt(efec_v), "#37474F") +
            _card("└ Yape", _fmt(yape_v), "#37474F") +
            _card("└ Plin", _fmt(plin_v), "#37474F") +
            _card("└ Transferencia", _fmt(transf_v), "#37474F"),
            unsafe_allow_html=True,
        )

    # ── B. INGRESOS ADICIONALES ──────────────────────────────
    with col_b:
        _section_header("B. Ingresos Adicionales")
        st.markdown(
            _card("Total ingresos adicionales", _fmt(total_ia), "#1565C0") +
            _card("└ Efectivo", _fmt(ia_efec), "#37474F") +
            _card("└ Yape", _fmt(ia_yape), "#37474F") +
            _card("└ Plin", _fmt(ia_plin), "#37474F") +
            _card("└ Transferencia", _fmt(ia_transf), "#37474F"),
            unsafe_allow_html=True,
        )

    col_c, col_d = st.columns(2)

    # ── C. EGRESOS Y OTROS ───────────────────────────────────
    with col_c:
        _section_header("C. Egresos y Otros")
        st.markdown(
            _card("Gastos", _fmt(total_gastos), "#D32F2F") +
            _card("Entrega de sobres", _fmt(total_sobres), "#E65100"),
            unsafe_allow_html=True,
        )

    # ── D. CAJA CHICA ────────────────────────────────────────
    with col_d:
        _section_header("D. Caja Chica (no es ingreso)")
        cc_estado_color = "#2E7D32" if cc_diff == 0 else ("#1565C0" if cc_diff > 0 else "#D32F2F")
        st.markdown(
            _card("Monto base", _fmt(cc_base), "#546E7A") +
            _card("Dinero contado", _fmt(cc_contado), "#546E7A") +
            _card("Diferencia", _fmt(cc_diff), cc_estado_color) +
            _card("Sobrante", _fmt(cc_sobrante), "#1565C0") +
            _card("Faltante", _fmt(cc_faltante), "#D32F2F") +
            _card("Estado", cc_estado, cc_estado_color),
            unsafe_allow_html=True,
        )

    # ── E. RESUMEN GENERAL ───────────────────────────────────
    st.divider()
    _section_header("E. Resumen General")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💰 Ventas totales", _fmt(total_vendido))
    col2.metric("➕ Ingresos adicionales", _fmt(total_ia))
    col3.metric("📋 Gastos", _fmt(total_gastos))
    utilidad_delta = "positivo" if utilidad >= 0 else "negativo"
    col4.metric(
        "🏆 Total neto del periodo",
        _fmt(utilidad),
        help="Ventas + Ingresos adicionales − Gastos − Sobres. Caja Chica NO incluida.",
    )
    if utilidad >= 0:
        st.success(f"✅ Resultado positivo del periodo: **{_fmt(utilidad)}**")
    else:
        st.error(f"⚠️ Resultado negativo del periodo: **{_fmt(utilidad)}**")


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
