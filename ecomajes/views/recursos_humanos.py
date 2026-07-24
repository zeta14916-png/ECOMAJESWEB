"""Recursos Humanos (RH) view for ECOMAJES ERP (GERENCIA > Recursos Humanos).

Tabs:
1. Empleados  — create, edit, activate/deactivate.  Fields: nombre, usuario,
   contraseña, documento, cargo, rol, sede, estado, teléfono, dirección,
   fecha de ingreso, salario.  No se eliminan empleados con historial.
2. Asistencias — leer registros de Control de Asistencia (Operario + Adm.).
   Filtros: trabajador, fecha, sede, tipo.
3. Tardanzas  — detecta tardanzas según el parámetro system_param
   ``horario_entrada`` y ``tolerancia_tardanza_min``.  Sin parámetro
   configurado, no inventa horarios.
4. Nómina     — registrar y consultar pagos (salario + bono − adelanto −
   descuento).  Cada pago queda en payroll_payments para Balance Financiero.

Passwords are stored salted+hashed by the data layer; they are NEVER shown.
"""

from datetime import date, time as dtime, datetime
from decimal import Decimal

import streamlit as st

from ecomajes import config, db

_STATUS_KEYS = list(db.EMPLOYEE_STATUS_LABELS.keys())


def _status_label(key: str) -> str:
    return db.EMPLOYEE_STATUS_LABELS.get(key, key)


def _money(value) -> float:
    return float(value) if value is not None else 0.0


# --------------------------------------------------------------------------- #
# Helpers for employee table display
# --------------------------------------------------------------------------- #
def _employee_rows(employees: list[dict]) -> list[dict]:
    """Shape employee rows for the table (passwords are NEVER included)."""
    rows = []
    for e in employees:
        rows.append(
            {
                "Nombre": e["nombre"],
                "Usuario": e["username"],
                "Documento": e.get("documento") or "—",
                "Cargo": e.get("cargo") or "—",
                "Rol": e["rol"],
                "Sede": e.get("sede") or "—",
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
# Tab 1 — Empleados
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
                documento = st.text_input("Documento de identidad")
            with col2:
                cargo = st.text_input("Cargo")
                sede = st.selectbox("Sede", [config.SEDE_PRINCIPAL, config.SEDE_SUCURSAL])
                telefono = st.text_input("Teléfono")
                direccion = st.text_input("Dirección")
                fecha_ingreso = st.date_input("Fecha de ingreso", value=date.today())
                salario = st.number_input("Salario", min_value=0.0, value=0.0, step=50.0)
            estado = st.selectbox("Estado", _STATUS_KEYS, format_func=_status_label)
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
                    documento=documento.strip() or None,
                    cargo=cargo.strip() or None,
                    sede=sede,
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

        sede_opts = [config.SEDE_PRINCIPAL, config.SEDE_SUCURSAL]

        with st.form(f"edit_employee_form_{selected_id}"):
            col1, col2 = st.columns(2)
            with col1:
                nombre = st.text_input("Nombre completo", value=emp["nombre"])
                username = st.text_input("Nombre de usuario", value=emp["username"])
                password = st.text_input(
                    "Nueva contraseña (dejar vacío para conservar)", type="password"
                )
                current_rol = (
                    emp["rol"] if emp["rol"] in config.ROLES else config.ROLES[0]
                )
                rol = st.selectbox(
                    "Rol", config.ROLES, index=config.ROLES.index(current_rol)
                )
                documento = st.text_input(
                    "Documento de identidad", value=emp.get("documento") or ""
                )
            with col2:
                cargo = st.text_input("Cargo", value=emp.get("cargo") or "")
                emp_sede = emp.get("sede")
                sede = st.selectbox(
                    "Sede",
                    sede_opts,
                    index=sede_opts.index(emp_sede) if emp_sede in sede_opts else 0,
                )
                telefono = st.text_input("Teléfono", value=emp["telefono"] or "")
                direccion = st.text_input("Dirección", value=emp["direccion"] or "")
                fecha_ingreso = st.date_input(
                    "Fecha de ingreso",
                    value=emp["fecha_ingreso"] or date.today(),
                )
                salario = st.number_input(
                    "Salario", min_value=0.0, value=_money(emp["salario"]), step=50.0
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
                    documento=documento.strip() or None,
                    cargo=cargo.strip() or None,
                    sede=sede,
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


def _tab_empleados(ctx: dict) -> list[dict]:
    # Filters
    col_search, col_sede, col_estado = st.columns(3)
    with col_search:
        search = st.text_input("🔍 Buscar (nombre / usuario / doc / cargo)", key="rh_employee_search")
    with col_sede:
        sede_opts = ["Todas", config.SEDE_PRINCIPAL, config.SEDE_SUCURSAL]
        sede_filter = st.selectbox("Sede", sede_opts, key="rh_emp_sede")
    with col_estado:
        estado_opts = ["Todos", "Activos", "Inactivos"]
        estado_filter = st.selectbox("Estado", estado_opts, key="rh_emp_estado")

    include_inactive = estado_filter != "Activos"
    employees = db.list_employees(
        search=search.strip() or None,
        include_inactive=include_inactive,
        sede=None if sede_filter == "Todas" else sede_filter,
    )

    # If user chose "Inactivos only", filter
    if estado_filter == "Inactivos":
        employees = [e for e in employees if e["estado"] == db.EMPLOYEE_INACTIVO]

    if employees:
        st.dataframe(
            _employee_rows(employees), use_container_width=True, hide_index=True
        )
        st.caption(f"{len(employees)} empleado(s) encontrado(s).")
    else:
        st.info("No hay empleados registrados para el filtro seleccionado.")

    if ctx["editable"]:
        _create_employee_form()
        _edit_employee_form(employees)
    return employees


# --------------------------------------------------------------------------- #
# Tab 2 — Asistencias
# --------------------------------------------------------------------------- #
def _tab_asistencias() -> None:
    st.caption(
        "Registros de entrada/salida desde Control de Asistencia (Operarios y Área Administrativa)."
    )
    col1, col2, col3, col4 = st.columns(4)
    today = date.today()
    month_start = today.replace(day=1)
    with col1:
        trabajador = st.text_input("Trabajador", key="rh_asi_trab")
    with col2:
        sede_opts = ["Todas", config.SEDE_PRINCIPAL, config.SEDE_SUCURSAL]
        sede_sel = st.selectbox("Sede", sede_opts, key="rh_asi_sede")
    with col3:
        from_date = st.date_input("Desde", value=month_start, key="rh_asi_from")
    with col4:
        to_date = st.date_input("Hasta", value=today, key="rh_asi_to")

    tipo_opts = ["Todos", "Entrada", "Salida"]
    tipo_sel = st.selectbox("Tipo de registro", tipo_opts, key="rh_asi_tipo")

    registros = db.list_attendance(
        sede=None if sede_sel == "Todas" else sede_sel,
        trabajador=trabajador.strip() or None,
        date_from=from_date,
        date_to=to_date,
        limit=500,
    )

    if tipo_sel != "Todos":
        tipo_key = "entrada" if tipo_sel == "Entrada" else "salida"
        registros = [r for r in registros if r["tipo"] == tipo_key]

    if not registros:
        st.info("No hay registros de asistencia para el filtro seleccionado.")
        return

    rows = [
        {
            "Fecha": r["fecha"].strftime("%d/%m/%Y"),
            "Hora": str(r["hora"])[:5],
            "Trabajador": r["trabajador"],
            "Tipo": "🟢 Entrada" if r["tipo"] == "entrada" else "🔴 Salida",
            "Sede": r["sede"],
            "Observaciones": r["observaciones"] or "—",
            "Registrado por": r["usuario_rol"] or "—",
        }
        for r in registros
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.caption(f"{len(rows)} registro(s) encontrado(s).")


# --------------------------------------------------------------------------- #
# Tab 3 — Tardanzas
# --------------------------------------------------------------------------- #
def _tab_tardanzas() -> None:
    st.caption("Detecta tardanzas según los parámetros de horario configurados en Configuración > Parámetros.")

    # Check parameters exist
    horario_str = db.get_system_param("horario_entrada", "")
    tolerancia_str = db.get_system_param("tolerancia_tardanza_min", "")

    if not horario_str:
        st.warning(
            "⚠️ No hay horario de entrada configurado. "
            "Ve a **Configuración > Parámetros** y define la hora de entrada "
            "antes de consultar tardanzas."
        )
        return

    try:
        h, m = horario_str.split(":")
        hora_entrada = dtime(int(h), int(m))
    except (ValueError, TypeError):
        st.error(f"El parámetro «horario_entrada» tiene un formato inválido: «{horario_str}». Use HH:MM.")
        return

    tolerancia = 0
    if tolerancia_str:
        try:
            tolerancia = int(tolerancia_str)
        except ValueError:
            tolerancia = 0

    hora_limite = dtime(
        hora_entrada.hour,
        hora_entrada.minute + tolerancia if hora_entrada.minute + tolerancia < 60 else 59,
    )

    # Filters
    today = date.today()
    month_start = today.replace(day=1)
    col1, col2, col3 = st.columns(3)
    with col1:
        trabajador = st.text_input("Trabajador", key="rh_tard_trab")
    with col2:
        from_date = st.date_input("Desde", value=month_start, key="rh_tard_from")
    with col3:
        to_date = st.date_input("Hasta", value=today, key="rh_tard_to")

    entradas = db.list_attendance(
        trabajador=trabajador.strip() or None,
        date_from=from_date,
        date_to=to_date,
        limit=1000,
    )
    entradas = [r for r in entradas if r["tipo"] == "entrada"]

    tardanzas = []
    for r in entradas:
        hora_reg = r["hora"]
        # hora_reg may be a datetime.time or timedelta
        if hasattr(hora_reg, "hour"):
            t = hora_reg
        else:
            # timedelta from psycopg2 for TIME columns
            total_sec = int(hora_reg.total_seconds())
            t = dtime(total_sec // 3600, (total_sec % 3600) // 60, total_sec % 60)

        if t > hora_limite:
            esperada_min = hora_entrada.hour * 60 + hora_entrada.minute
            real_min = t.hour * 60 + t.minute
            minutos_tarde = real_min - esperada_min
            tardanzas.append({
                "Fecha": r["fecha"].strftime("%d/%m/%Y"),
                "Trabajador": r["trabajador"],
                "Sede": r["sede"],
                "Hora esperada": hora_entrada.strftime("%H:%M"),
                "Hora registrada": f"{t.hour:02d}:{t.minute:02d}",
                "Minutos de tardanza": minutos_tarde,
                "Justificación": r["observaciones"] or "—",
            })

    if not tardanzas:
        st.success("✅ No se detectaron tardanzas en el período seleccionado.")
        return

    st.warning(f"⚠️ {len(tardanzas)} tardanza(s) detectada(s).")
    st.caption(
        f"Hora de entrada configurada: **{hora_entrada.strftime('%H:%M')}** · "
        f"Tolerancia: **{tolerancia} min**"
    )
    st.dataframe(tardanzas, use_container_width=True, hide_index=True)


# --------------------------------------------------------------------------- #
# Tab 4 — Nómina
# --------------------------------------------------------------------------- #
def _payroll_form(ctx: dict, employees: list[dict]) -> None:
    active = [e for e in employees if e["estado"] == db.EMPLOYEE_ACTIVO]
    if not active:
        st.caption("Registre un empleado activo para poder pagar la nómina.")
        return

    by_id = {e["id"]: e for e in active}
    with st.expander("➕ Registrar pago de nómina"):
        selected_id = st.selectbox(
            "Empleado",
            list(by_id.keys()),
            format_func=lambda i: f"{by_id[i]['nombre']} ({by_id[i]['username']})",
            key="payroll_employee_select",
        )
        default_salary = _money(by_id[selected_id]["salario"])
        if st.session_state.get("_payroll_last_emp") != selected_id:
            st.session_state["_payroll_last_emp"] = selected_id
            st.session_state["payroll_salario"] = default_salary

        col1, col2 = st.columns(2)
        with col1:
            fecha = st.date_input("Fecha", value=date.today(), key="payroll_date")
            salario = st.number_input(
                "Pago mensual (salario)", min_value=0.0, step=50.0, key="payroll_salario"
            )
            bono = st.number_input(
                "Bono", min_value=0.0, value=0.0, step=50.0, key="payroll_bono"
            )
        with col2:
            adelanto = st.number_input(
                "Adelanto", min_value=0.0, value=0.0, step=50.0, key="payroll_adelanto"
            )
            descuento = st.number_input(
                "Descuento", min_value=0.0, value=0.0, step=50.0, key="payroll_descuento"
            )
        observacion = st.text_area("Observación", key="payroll_obs")

        pago_final = salario + bono - adelanto - descuento
        st.markdown(f"**Pago final: S/ {pago_final:,.2f}**")

        if st.button("Registrar pago", key="payroll_submit"):
            if pago_final < 0:
                st.error(
                    "El pago final no puede ser negativo. Revise adelanto y descuento."
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
                for _k in (
                    "payroll_salario", "payroll_bono", "payroll_adelanto",
                    "payroll_descuento", "payroll_obs", "_payroll_last_emp",
                ):
                    st.session_state.pop(_k, None)
                db.log_audit(
                    db.AUDIT_PAYROLL,
                    "Recursos Humanos",
                    detalle=(
                        f"{by_id[selected_id]['nombre']} · S/ {pago_final:,.2f}"
                    ),
                    usuario_rol=ctx["usuario_rol"],
                )
                st.success(f"Pago registrado. Pago final: S/ {pago_final:,.2f}")
                st.rerun()


def _payment_history(employees: list[dict]) -> None:
    st.subheader("📜 Historial de pagos")

    options: dict = {None: "Todos los empleados"}
    for e in employees:
        options[e["id"]] = f"{e['nombre']} ({e['username']})"
    col1, col2, col3 = st.columns(3)
    with col1:
        emp_filter = st.selectbox(
            "Empleado", list(options.keys()),
            format_func=lambda i: options[i], key="history_employee_filter"
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
    st.metric("Total pagado (filtro actual)", f"S/ {total:,.2f}")


def _tab_nomina(ctx: dict, employees: list[dict]) -> None:
    if ctx["editable"]:
        _payroll_form(ctx, employees)
    _payment_history(employees)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def render(ctx: dict) -> None:
    st.header(ctx["title"])
    st.caption(ctx["breadcrumb"])

    tabs = st.tabs(["👥 Empleados", "📋 Asistencias", "⏰ Tardanzas", "💵 Nómina"])

    with tabs[0]:
        employees = _tab_empleados(ctx)

    with tabs[1]:
        _tab_asistencias()

    with tabs[2]:
        _tab_tardanzas()

    with tabs[3]:
        # Re-fetch all employees (tabs share no state)
        all_employees = db.list_employees()
        _tab_nomina(ctx, all_employees)
