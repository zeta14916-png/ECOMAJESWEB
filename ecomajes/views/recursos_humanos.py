"""Recursos Humanos (RH) view for ECOMAJES ERP (GERENCIA > Recursos Humanos).

Two areas on one screen:

1. **Empleados** — create, edit and activate/deactivate employees (nombre,
   usuario, contraseña, rol, estado, teléfono, dirección, fecha de ingreso,
   salario). Passwords are stored salted+hashed by the data layer.
2. **Nómina** — register a monthly payroll payment (salario + bono − adelanto −
   descuento = pago final) and browse the full payment history.

Every payment is stored in ``payroll_payments`` and exposed through
``db.payroll_total`` so Balance Financiero can consume it later. Balance
Financiero itself is intentionally left untouched (integration only prepared).
"""

from datetime import date
from decimal import Decimal

import streamlit as st

from ecomajes import config, db

_STATUS_KEYS = list(db.EMPLOYEE_STATUS_LABELS.keys())


def _status_label(key: str) -> str:
    return db.EMPLOYEE_STATUS_LABELS.get(key, key)


def _money(value) -> float:
    return float(value) if value is not None else 0.0


def _employee_rows(employees: list[dict]) -> list[dict]:
    """Shape employee rows for the table (never exposes passwords)."""
    rows = []
    for e in employees:
        rows.append(
            {
                "Nombre": e["nombre"],
                "Usuario": e["username"],
                "Rol": e["rol"],
                "Estado": _status_label(e["estado"]),
                "Teléfono": e["telefono"] or "—",
                "Dirección": e["direccion"] or "—",
                "Fecha de ingreso": (
                    e["fecha_ingreso"].strftime("%Y-%m-%d")
                    if e["fecha_ingreso"]
                    else "—"
                ),
                "Salario": _money(e["salario"]),
            }
        )
    return rows


# --------------------------------------------------------------------------- #
# Empleados (employee management)
# --------------------------------------------------------------------------- #
def _create_employee_form() -> None:
    with st.expander("➕ Registrar empleado"):
        with st.form("create_employee_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                nombre = st.text_input("Nombre completo")
                username = st.text_input("Nombre de usuario")
                password = st.text_input("Contraseña", type="password")
                rol = st.selectbox("Rol", config.ROLES)
            with col2:
                telefono = st.text_input("Teléfono")
                direccion = st.text_input("Dirección")
                fecha_ingreso = st.date_input(
                    "Fecha de ingreso", value=date.today()
                )
                salario = st.number_input(
                    "Salario", min_value=0.0, value=0.0, step=50.0
                )
            estado = st.selectbox(
                "Estado", _STATUS_KEYS, format_func=_status_label
            )
            submitted = st.form_submit_button("Guardar empleado")

        if submitted:
            if not nombre.strip():
                st.error("El nombre completo es obligatorio.")
                return
            if not username.strip():
                st.error("El nombre de usuario es obligatorio.")
                return
            if not password:
                st.error("La contraseña es obligatoria.")
                return
            try:
                db.create_employee(
                    nombre=nombre.strip(),
                    username=username.strip(),
                    password=password,
                    rol=rol,
                    estado=estado,
                    telefono=telefono.strip() or None,
                    direccion=direccion.strip() or None,
                    fecha_ingreso=fecha_ingreso,
                    salario=Decimal(str(salario)),
                )
            except db.EmployeeError as exc:
                st.error(str(exc))
            except Exception as exc:  # noqa: BLE001
                st.error(f"No se pudo guardar el empleado: {exc}")
            else:
                st.success(f"Empleado «{nombre.strip()}» registrado.")
                st.rerun()


def _edit_employee_form(employees: list[dict]) -> None:
    if not employees:
        return
    with st.expander("✏️ Editar empleado"):
        by_id = {e["id"]: e for e in employees}
        selected_id = st.selectbox(
            "Empleado a editar",
            list(by_id.keys()),
            format_func=lambda i: f"{by_id[i]['nombre']} ({by_id[i]['username']})",
            key="edit_employee_select",
        )
        emp = by_id[selected_id]

        with st.form(f"edit_employee_form_{selected_id}"):
            col1, col2 = st.columns(2)
            with col1:
                nombre = st.text_input("Nombre completo", value=emp["nombre"])
                username = st.text_input(
                    "Nombre de usuario", value=emp["username"]
                )
                password = st.text_input(
                    "Nueva contraseña (dejar vacío para conservar)",
                    type="password",
                )
                current_rol = (
                    emp["rol"] if emp["rol"] in config.ROLES else config.ROLES[0]
                )
                rol = st.selectbox(
                    "Rol",
                    config.ROLES,
                    index=config.ROLES.index(current_rol),
                )
            with col2:
                telefono = st.text_input("Teléfono", value=emp["telefono"] or "")
                direccion = st.text_input(
                    "Dirección", value=emp["direccion"] or ""
                )
                fecha_ingreso = st.date_input(
                    "Fecha de ingreso",
                    value=emp["fecha_ingreso"] or date.today(),
                )
                salario = st.number_input(
                    "Salario",
                    min_value=0.0,
                    value=_money(emp["salario"]),
                    step=50.0,
                )
            estado = st.selectbox(
                "Estado",
                _STATUS_KEYS,
                index=_STATUS_KEYS.index(emp["estado"])
                if emp["estado"] in _STATUS_KEYS
                else 0,
                format_func=_status_label,
            )
            submitted = st.form_submit_button("Guardar cambios")

        if submitted:
            if not nombre.strip():
                st.error("El nombre completo es obligatorio.")
                return
            if not username.strip():
                st.error("El nombre de usuario es obligatorio.")
                return
            try:
                db.update_employee(
                    employee_id=selected_id,
                    nombre=nombre.strip(),
                    username=username.strip(),
                    rol=rol,
                    estado=estado,
                    telefono=telefono.strip() or None,
                    direccion=direccion.strip() or None,
                    fecha_ingreso=fecha_ingreso,
                    salario=Decimal(str(salario)),
                    password=password or None,
                )
            except db.EmployeeError as exc:
                st.error(str(exc))
            except Exception as exc:  # noqa: BLE001
                st.error(f"No se pudo actualizar el empleado: {exc}")
            else:
                st.success("Empleado actualizado.")
                st.rerun()

        st.divider()
        estado_txt = _status_label(emp["estado"])
        st.caption(f"Estado actual: **{estado_txt}**")
        if emp["estado"] == db.EMPLOYEE_ACTIVO:
            if st.button("🚫 Desactivar empleado", key=f"deact_emp_{selected_id}"):
                db.set_employee_status(selected_id, db.EMPLOYEE_INACTIVO)
                st.success("Empleado desactivado.")
                st.rerun()
        else:
            if st.button("✅ Activar empleado", key=f"act_emp_{selected_id}"):
                db.set_employee_status(selected_id, db.EMPLOYEE_ACTIVO)
                st.success("Empleado activado.")
                st.rerun()


def _employees_section(ctx: dict) -> list[dict]:
    st.subheader("👥 Empleados")
    search = st.text_input(
        "🔍 Buscar por nombre o usuario", key="rh_employee_search"
    )
    employees = db.list_employees(search=search.strip() or None)

    if employees:
        st.dataframe(
            _employee_rows(employees), use_container_width=True, hide_index=True
        )
    else:
        st.info("No hay empleados registrados todavía.")

    if ctx["editable"]:
        _create_employee_form()
        _edit_employee_form(employees)
    return employees


# --------------------------------------------------------------------------- #
# Nómina (payroll + payment history)
# --------------------------------------------------------------------------- #
def _payroll_form(ctx: dict, employees: list[dict]) -> None:
    active = [e for e in employees if e["estado"] == db.EMPLOYEE_ACTIVO]
    if not active:
        st.caption("Registre un empleado activo para poder pagar la nómina.")
        return

    by_id = {e["id"]: e for e in active}
    with st.expander("➕ Registrar pago de nómina", expanded=not _has_payments()):
        # Inputs live outside a form so the "Pago final" preview updates live
        # as the amounts change.
        selected_id = st.selectbox(
            "Empleado",
            list(by_id.keys()),
            format_func=lambda i: f"{by_id[i]['nombre']} ({by_id[i]['username']})",
            key="payroll_employee_select",
        )
        default_salary = _money(by_id[selected_id]["salario"])
        # Prefill the salary with the employee's base salary whenever the
        # selected employee changes.
        if st.session_state.get("_payroll_last_emp") != selected_id:
            st.session_state["_payroll_last_emp"] = selected_id
            st.session_state["payroll_salario"] = default_salary

        col1, col2 = st.columns(2)
        with col1:
            fecha = st.date_input("Fecha", value=date.today(), key="payroll_date")
            salario = st.number_input(
                "Pago mensual (salario)",
                min_value=0.0,
                step=50.0,
                key="payroll_salario",
            )
            bono = st.number_input(
                "Bono", min_value=0.0, value=0.0, step=50.0, key="payroll_bono"
            )
        with col2:
            adelanto = st.number_input(
                "Adelanto",
                min_value=0.0,
                value=0.0,
                step=50.0,
                key="payroll_adelanto",
            )
            descuento = st.number_input(
                "Descuento",
                min_value=0.0,
                value=0.0,
                step=50.0,
                key="payroll_descuento",
            )
        observacion = st.text_area("Observación", key="payroll_obs")

        pago_final = salario + bono - adelanto - descuento
        st.markdown(f"**Pago final: $ {pago_final:,.2f}**")

        if st.button("Registrar pago", key="payroll_submit"):
            if pago_final < 0:
                st.error(
                    "El pago final no puede ser negativo. "
                    "Revise adelanto y descuento."
                )
                return
            try:
                db.register_payroll_payment(
                    employee_id=selected_id,
                    fecha=fecha,
                    salario=Decimal(str(salario)),
                    bono=Decimal(str(bono)),
                    adelanto=Decimal(str(adelanto)),
                    descuento=Decimal(str(descuento)),
                    observacion=observacion.strip() or None,
                    usuario_rol=ctx["usuario_rol"],
                )
            except Exception as exc:  # noqa: BLE001
                st.error(f"No se pudo registrar el pago: {exc}")
            else:
                # Reset the amount fields for the next payment.
                for _k in (
                    "payroll_salario",
                    "payroll_bono",
                    "payroll_adelanto",
                    "payroll_descuento",
                    "payroll_obs",
                    "_payroll_last_emp",
                ):
                    st.session_state.pop(_k, None)
                st.success(f"Pago registrado. Pago final: $ {pago_final:,.2f}")
                st.rerun()


def _has_payments() -> bool:
    return bool(db.list_payroll_payments())


def _payment_history(employees: list[dict]) -> None:
    st.subheader("📜 Historial de pagos")

    options: dict = {None: "Todos los empleados"}
    for e in employees:
        options[e["id"]] = f"{e['nombre']} ({e['username']})"
    col1, col2, col3 = st.columns(3)
    with col1:
        emp_filter = st.selectbox(
            "Empleado",
            list(options.keys()),
            format_func=lambda i: options[i],
            key="history_employee_filter",
        )
    with col2:
        date_from = st.date_input("Desde", value=None, key="history_from")
    with col3:
        date_to = st.date_input("Hasta", value=None, key="history_to")

    payments = db.list_payroll_payments(
        employee_id=emp_filter,
        date_from=date_from or None,
        date_to=date_to or None,
    )
    if not payments:
        st.caption("No hay pagos registrados para el filtro seleccionado.")
        return

    rows = [
        {
            "Empleado": p["empleado"],
            "Fecha": p["fecha"].strftime("%Y-%m-%d"),
            "Salario": _money(p["salario"]),
            "Bono": _money(p["bono"]),
            "Adelanto": _money(p["adelanto"]),
            "Descuento": _money(p["descuento"]),
            "Pago final": _money(p["pago_final"]),
            "Observación": p["observacion"] or "—",
            "Registrado por": p["usuario_rol"] or "—",
        }
        for p in payments
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    total = sum(_money(p["pago_final"]) for p in payments)
    st.metric("Total pagado (filtro actual)", f"$ {total:,.2f}")


def _payroll_section(ctx: dict, employees: list[dict]) -> None:
    st.subheader("💵 Nómina")
    if ctx["editable"]:
        _payroll_form(ctx, employees)
    _payment_history(employees)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def render(ctx: dict) -> None:
    st.header(ctx["title"])
    st.caption(ctx["breadcrumb"])

    employees = _employees_section(ctx)
    st.divider()
    _payroll_section(ctx, employees)
