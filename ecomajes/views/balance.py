"""Balance Financiero view for ECOMAJES ERP (GERENCIA > Balance Financiero).

Full financial dashboard with:
- Tabs: Resumen | Ingresos | Egresos | Caja Chica | Gráficos | Alertas
- Period filters: Diario, Semanal, Mensual, Anual or custom range.
- Sede scope: Sede Principal, Sucursal, Empresa Completa.
- Payroll payments are counted as Egresos (labor cost).
- Caja Chica is shown separately — NOT as income.
- Ingresos adicionales add to total revenue.
"""

from collections import Counter
from datetime import date, timedelta
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
# Period helpers
# --------------------------------------------------------------------------- #
def _period_dates(periodo: str) -> tuple[date, date]:
    today = date.today()
    if periodo == "Diario":
        return today, today
    if periodo == "Semanal":
        start = today - timedelta(days=today.weekday())
        return start, today
    if periodo == "Mensual":
        return today.replace(day=1), today
    if periodo == "Anual":
        return today.replace(month=1, day=1), today
    # Custom — caller provides dates
    return today.replace(day=1), today


# --------------------------------------------------------------------------- #
# Filters
# --------------------------------------------------------------------------- #
def _filters() -> dict:
    today = date.today()
    month_start = today.replace(day=1)

    col1, col2 = st.columns(2)
    with col1:
        ubicacion = st.selectbox("Ubicación", _LOCATIONS, key="bal_ubicacion")
    with col2:
        periodo = st.selectbox(
            "Período",
            ["Diario", "Semanal", "Mensual", "Anual", "Personalizado"],
            index=2,
            key="bal_periodo",
        )

    sede, include_all = _scope(ubicacion)

    if periodo == "Personalizado":
        c1, c2 = st.columns(2)
        with c1:
            date_from = st.date_input("Desde", value=month_start, key="bal_from")
        with c2:
            date_to = st.date_input("Hasta", value=today, key="bal_to")
    else:
        date_from, date_to = _period_dates(periodo)
        st.caption(
            f"Período: **{periodo}** · {date_from.strftime('%d/%m/%Y')} → {date_to.strftime('%d/%m/%Y')}"
        )

    if date_from > date_to:
        st.warning("El rango de fechas es inválido: 'Desde' es posterior a 'Hasta'.")
        date_from, date_to = date_to, date_from

    categorias = [_TODAS] + db.list_categories(sede, include_all)
    categoria = st.selectbox("Categoría de inventario", categorias, key="bal_cat")

    return {
        "ubicacion": ubicacion,
        "sede": sede,
        "include_all": include_all,
        "date_from": date_from,
        "date_to": date_to,
        "categoria": None if categoria == _TODAS else categoria,
        "today": today,
        "month_start": month_start,
        "periodo": periodo,
    }


# --------------------------------------------------------------------------- #
# Financial summary with payroll included
# --------------------------------------------------------------------------- #
def _full_summary(f: dict) -> dict:
    """Aggregate revenue + expenses + payroll for the selected scope/period."""
    fin = db.financial_summary(
        sede=f["sede"],
        include_all_sedes=f["include_all"],
        date_from=f["date_from"],
        date_to=f["date_to"],
    )
    # Ingresos adicionales
    ing_adicionales = db.list_ingresos_adicionales(
        sede=f["sede"],
        include_all_sedes=f["include_all"],
        date_from=f["date_from"],
        date_to=f["date_to"],
    )
    total_ingresos_adicionales = sum(_money(r["monto"]) for r in ing_adicionales)

    # Payroll (labor expense, scoped by employee sede)
    payroll = float(
        db.payroll_total_by_sede(
            sede=f["sede"],
            include_all_sedes=f["include_all"],
            date_from=f["date_from"],
            date_to=f["date_to"],
        )
    )

    total_revenue = _money(fin["total_revenue"]) + total_ingresos_adicionales
    total_expenses = _money(fin["total_expenses"]) + payroll
    utilidad = total_revenue - total_expenses

    # "Inversión" = total stock value (informational)
    inv = db.list_inventory(f["sede"], f["include_all"])
    inversion = 0.0
    for p in inv:
        precio = 0.0
        try:
            with db._get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT costo FROM prices WHERE product_id = %s", (p["id"],)
                    )
                    row = cur.fetchone()
                    if row and row[0]:
                        precio = float(row[0])
        except Exception:
            pass
        inversion += precio * float(p["stock"])

    return {
        "ventas": _money(fin["total_revenue"]),
        "ingresos_adicionales": total_ingresos_adicionales,
        "total_revenue": total_revenue,
        "gastos": _money(fin["total_expenses"]),
        "nomina": payroll,
        "total_expenses": total_expenses,
        "utilidad": utilidad,
        "inversion": inversion,
        "ganancia_neta": utilidad,  # utilidad after deducting investment is informational
        "total_products": fin["total_products"],
        "_ing_adicionales": ing_adicionales,
    }


# --------------------------------------------------------------------------- #
# Tab: Resumen (KPI cards)
# --------------------------------------------------------------------------- #
def _tab_resumen(f: dict) -> None:
    summary = _full_summary(f)

    st.caption(
        f"📍 **{f['ubicacion']}** · {f['date_from'].strftime('%d/%m/%Y')} → {f['date_to'].strftime('%d/%m/%Y')}"
    )
    st.divider()

    st.markdown("#### 💰 Ingresos")
    r1 = st.columns(3)
    r1[0].metric("Ventas", f"S/ {summary['ventas']:,.2f}")
    r1[1].metric("Ingresos adicionales", f"S/ {summary['ingresos_adicionales']:,.2f}")
    r1[2].metric("Total ingresos", f"S/ {summary['total_revenue']:,.2f}")

    st.markdown("#### 📤 Egresos")
    r2 = st.columns(3)
    r2[0].metric("Gastos", f"S/ {summary['gastos']:,.2f}")
    r2[1].metric("Nómina (RR.HH.)", f"S/ {summary['nomina']:,.2f}")
    r2[2].metric("Total egresos", f"S/ {summary['total_expenses']:,.2f}")

    st.divider()
    r3 = st.columns(3)
    delta_color = "normal" if summary["utilidad"] >= 0 else "inverse"
    r3[0].metric(
        "Utilidad",
        f"S/ {summary['utilidad']:,.2f}",
        delta=f"{'+'  if summary['utilidad'] >= 0 else ''}{summary['utilidad']:,.2f}",
        delta_color=delta_color,
    )
    r3[1].metric(
        "Inversión en stock",
        f"S/ {summary['inversion']:,.2f}",
        help="Valor al costo del inventario actual.",
    )
    r3[2].metric("Ganancia neta (utilidad)", f"S/ {summary['ganancia_neta']:,.2f}")

    # Inventory alerts summary
    inv = db.list_inventory(f["sede"], f["include_all"])
    agotados = [p for p in inv if Decimal(p["stock"]) <= 0]
    bajo = [
        p for p in inv
        if Decimal("0") < Decimal(p["stock"]) <= db.LOW_STOCK_THRESHOLD
    ]
    st.divider()
    r4 = st.columns(2)
    r4[0].metric("Productos con stock bajo", len(bajo))
    r4[1].metric("Productos agotados", len(agotados))


# --------------------------------------------------------------------------- #
# Tab: Ingresos
# --------------------------------------------------------------------------- #
def _tab_ingresos(f: dict) -> None:
    st.subheader("💰 Ingresos")

    # Sales
    st.markdown("**Ventas (movimientos de tipo venta)**")
    ventas = db.list_sales(
        sede=f["sede"],
        include_all_sedes=f["include_all"],
        date_from=f["date_from"],
        date_to=f["date_to"],
    )
    if ventas:
        rows_v = [
            {
                "Fecha": v["created_at"].strftime("%d/%m/%Y %H:%M"),
                "Producto": v["producto"],
                "Sede": v["sede"],
                "Cantidad": float(v["cantidad"]),
                "Precio unitario": _money(v["precio_unitario"]),
                "Total": _money(v["precio_total"]),
                "Método pago": v.get("metodo_pago") or "—",
                "Usuario": v["usuario_rol"] or "—",
            }
            for v in ventas
        ]
        st.dataframe(rows_v, use_container_width=True, hide_index=True)
        total_v = sum(_money(v["precio_total"]) for v in ventas)
        st.metric("Total ventas", f"S/ {total_v:,.2f}")
    else:
        st.caption("Sin ventas en el período seleccionado.")

    st.divider()
    st.markdown("**Ingresos adicionales**")
    ing = db.list_ingresos_adicionales(
        sede=f["sede"],
        include_all_sedes=f["include_all"],
        date_from=f["date_from"],
        date_to=f["date_to"],
    )
    if ctx_editable := st.session_state.get("_bal_editable", False):
        with st.expander("➕ Registrar ingreso adicional"):
            with st.form("bal_ing_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                with c1:
                    ing_fecha = st.date_input("Fecha", value=date.today())
                    ing_sede = st.selectbox(
                        "Sede", [config.SEDE_PRINCIPAL, config.SEDE_SUCURSAL]
                    )
                with c2:
                    ing_desc = st.text_input("Descripción")
                    ing_monto = st.number_input("Monto", min_value=0.0, step=10.0)
                ing_sub = st.form_submit_button("Registrar")
            if ing_sub:
                if not ing_desc.strip():
                    st.error("La descripción es obligatoria.")
                else:
                    try:
                        db.add_ingreso_adicional(
                            fecha=ing_fecha,
                            sede=ing_sede,
                            descripcion=ing_desc.strip(),
                            monto=Decimal(str(ing_monto)),
                            usuario_rol=st.session_state.get("_bal_usuario"),
                        )
                        db.log_audit(
                            db.AUDIT_EXPENSE,
                            "Balance Financiero",
                            detalle=f"Ingreso adicional: {ing_desc.strip()} S/{ing_monto:,.2f}",
                            usuario_rol=st.session_state.get("_bal_usuario"),
                            sede=ing_sede,
                        )
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Error: {exc}")
                    else:
                        st.success("Ingreso adicional registrado.")
                        st.rerun()
    if ing:
        rows_i = [
            {
                "Fecha": r["fecha"].strftime("%d/%m/%Y"),
                "Sede": r["sede"],
                "Descripción": r["descripcion"],
                "Monto": _money(r["monto"]),
                "Registrado por": r["usuario_rol"] or "—",
            }
            for r in ing
        ]
        st.dataframe(rows_i, use_container_width=True, hide_index=True)
        total_i = sum(_money(r["monto"]) for r in ing)
        st.metric("Total ingresos adicionales", f"S/ {total_i:,.2f}")
    else:
        st.caption("Sin ingresos adicionales en el período.")


# --------------------------------------------------------------------------- #
# Tab: Egresos
# --------------------------------------------------------------------------- #
def _tab_egresos(f: dict) -> None:
    st.subheader("📤 Egresos")

    # Expenses
    st.markdown("**Gastos registrados**")
    expenses = db.list_expenses(
        sede=f["sede"],
        include_all_sedes=f["include_all"],
        date_from=f["date_from"],
        date_to=f["date_to"],
    )
    if expenses:
        rows_e = [
            {
                "Fecha": e["fecha"].strftime("%d/%m/%Y"),
                "Descripción": e["descripcion"],
                "Monto": _money(e["monto"]),
                "Sede": e["sede"],
                "Registrado por": e["usuario_rol"] or "—",
            }
            for e in expenses
        ]
        st.dataframe(rows_e, use_container_width=True, hide_index=True)
        total_e = sum(_money(e["monto"]) for e in expenses)
        st.metric("Total gastos", f"S/ {total_e:,.2f}")
    else:
        st.caption("Sin gastos en el período seleccionado.")

    st.divider()
    # Payroll
    st.markdown("**Pagos de nómina (Recursos Humanos)**")
    payments = db.list_payroll_payments(
        date_from=f["date_from"],
        date_to=f["date_to"],
    )
    if payments:
        rows_p = [
            {
                "Fecha": p["fecha"].strftime("%d/%m/%Y"),
                "Empleado": p["empleado"],
                "Salario": _money(p["salario"]),
                "Bono": _money(p["bono"]),
                "Adelanto": _money(p["adelanto"]),
                "Descuento": _money(p["descuento"]),
                "Pago final": _money(p["pago_final"]),
                "Registrado por": p["usuario_rol"] or "—",
            }
            for p in payments
        ]
        st.dataframe(rows_p, use_container_width=True, hide_index=True)
        total_p = sum(_money(p["pago_final"]) for p in payments)
        st.metric("Total nómina", f"S/ {total_p:,.2f}")
    else:
        st.caption("Sin pagos de nómina en el período seleccionado.")


# --------------------------------------------------------------------------- #
# Tab: Caja Chica
# --------------------------------------------------------------------------- #
def _tab_caja_chica(f: dict) -> None:
    st.subheader("💼 Caja Chica")
    st.info(
        "ℹ️ La Caja Chica es un **fondo fijo**. "
        "**No se considera ingreso** y se muestra aquí por separado. "
        "Para registrar revisiones de Caja Chica, ve a Configuración."
    )

    registros = db.list_caja_chica(
        sede=f["sede"],
        include_all_sedes=f["include_all"],
        date_from=f["date_from"],
        date_to=f["date_to"],
    )

    if not registros:
        st.caption("No hay registros de Caja Chica en el período seleccionado.")
        return

    rows = [
        {
            "Fecha": r["fecha"].strftime("%d/%m/%Y"),
            "Sede": r["sede"],
            "Monto base": _money(r["monto_base"]),
            "Contado": _money(r["dinero_contado"]),
            "Diferencia": _money(r["diferencia"]),
            "Observación": r["observaciones"] or "—",
            "Registrado por": r["usuario_rol"] or "—",
        }
        for r in registros
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)
    col1.metric("Registros", len(registros))
    diferencia_total = sum(_money(r["diferencia"]) for r in registros)
    col2.metric(
        "Diferencia acumulada",
        f"S/ {diferencia_total:,.2f}",
        help="Suma de diferencias (contado − base). Positivo = sobrante, negativo = faltante.",
    )


# --------------------------------------------------------------------------- #
# Tab: Gráficos
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


def _tab_graficos(f: dict) -> None:
    st.subheader("📊 Gráficos")

    a1, a2 = st.columns(2)
    with a1:
        st.markdown("**Ventas por día**")
        rows = db.sales_by_day(
            f["sede"], f["include_all"], f["date_from"], f["date_to"], f["categoria"]
        )
        if rows:
            df = pd.DataFrame(
                {str(r["dia"]): _money(r["total"]) for r in rows}.items(),
                columns=["Día", "Ventas"],
            ).set_index("Día")
            st.line_chart(df)
        else:
            st.caption("Sin datos.")

    with a2:
        st.markdown("**Ventas por mes**")
        rows = db.sales_by_month(
            f["sede"], f["include_all"], f["date_from"], f["date_to"], f["categoria"]
        )
        if rows:
            df = pd.DataFrame(
                {r["mes"]: _money(r["total"]) for r in rows}.items(),
                columns=["Mes", "Ventas"],
            ).set_index("Mes")
            st.bar_chart(df)
        else:
            st.caption("Sin datos.")

    b1, b2 = st.columns(2)
    with b1:
        st.markdown("**Productos más vendidos**")
        rows = db.sales_by_product(
            f["sede"], f["include_all"], f["date_from"], f["date_to"],
            f["categoria"], order="desc", limit=10,
        )
        if rows:
            labels = _product_labels(rows)
            df = pd.DataFrame(
                {"Producto": labels, "Unidades": [float(r["unidades"]) for r in rows]}
            ).set_index("Producto")
            st.bar_chart(df)
        else:
            st.caption("Sin datos.")

    with b2:
        st.markdown("**Productos menos vendidos**")
        rows = db.sales_by_product(
            f["sede"], f["include_all"], f["date_from"], f["date_to"],
            f["categoria"], order="asc", limit=10,
        )
        if rows:
            labels = _product_labels(rows)
            df = pd.DataFrame(
                {"Producto": labels, "Unidades": [float(r["unidades"]) for r in rows]}
            ).set_index("Producto")
            st.bar_chart(df)
        else:
            st.caption("Sin datos.")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Ventas por sede**")
        rows = db.sales_by_location(f["date_from"], f["date_to"], f["categoria"])
        if rows:
            df = pd.DataFrame(
                {r["sede"]: _money(r["total"]) for r in rows}.items(),
                columns=["Sede", "Ventas"],
            ).set_index("Sede")
            st.bar_chart(df)
        else:
            st.caption("Sin datos.")

    with c2:
        st.markdown("**Ingresos vs Gastos (por mes)**")
        sales = db.sales_by_month(
            f["sede"], f["include_all"], f["date_from"], f["date_to"], None
        )
        expenses = db.expenses_by_month(
            f["sede"], f["include_all"], f["date_from"], f["date_to"]
        )
        if sales or expenses:
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
        else:
            st.caption("Sin datos.")

    st.markdown("**Inventario por categoría**")
    inv = db.list_inventory(f["sede"], f["include_all"], f["categoria"])
    if inv:
        totals: dict[str, float] = {}
        for p in inv:
            totals[p["categoria"]] = totals.get(p["categoria"], 0.0) + float(p["stock"])
        df = pd.DataFrame(
            totals.items(), columns=["Categoría", "Stock"]
        ).set_index("Categoría")
        st.bar_chart(df)
    else:
        st.caption("Sin datos de inventario.")


# --------------------------------------------------------------------------- #
# Tab: Alertas
# --------------------------------------------------------------------------- #
def _tab_alertas(f: dict) -> None:
    st.subheader("⚠️ Alertas")
    inv = db.list_inventory(f["sede"], f["include_all"], f["categoria"])
    agotados = [p for p in inv if Decimal(p["stock"]) <= 0]
    bajo = [
        p for p in inv
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

    st.divider()
    st.markdown("**Últimos movimientos**")
    movs = db.list_movements(
        sede=f["sede"], include_all_sedes=f["include_all"], limit=10
    )
    if movs:
        st.dataframe(
            [
                {
                    "Fecha": m["created_at"].strftime("%d/%m/%Y %H:%M"),
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

    # Store editable + usuario in session for use in tabs
    st.session_state["_bal_editable"] = ctx.get("editable", False)
    st.session_state["_bal_usuario"] = ctx.get("usuario_rol")

    f = _filters()
    st.divider()

    tabs = st.tabs([
        "📊 Resumen",
        "💰 Ingresos",
        "📤 Egresos",
        "💼 Caja Chica",
        "📈 Gráficos",
        "⚠️ Alertas",
    ])

    with tabs[0]:
        _tab_resumen(f)

    with tabs[1]:
        _tab_ingresos(f)

    with tabs[2]:
        _tab_egresos(f)

    with tabs[3]:
        _tab_caja_chica(f)

    with tabs[4]:
        _tab_graficos(f)

    with tabs[5]:
        _tab_alertas(f)
