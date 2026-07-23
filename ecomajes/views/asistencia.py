"""Control de Asistencia view para ECOMAJES ERP (OPERARIOS).

Permite al operario registrar su entrada o salida indicando su nombre.
La fecha, hora y sede se registran automáticamente. La información queda
disponible para que Recursos Humanos la consulte posteriormente.
"""

from datetime import datetime

import streamlit as st

from ecomajes import db

TIPO_ENTRADA = "entrada"
TIPO_SALIDA = "salida"
_TIPO_LABELS = {TIPO_ENTRADA: "🟢 Entrada", TIPO_SALIDA: "🔴 Salida"}


def render(ctx: dict) -> None:
    st.header(ctx["title"])
    st.caption(ctx["breadcrumb"])

    st.subheader("📋 Registrar Asistencia")
    st.caption(
        f"Sede: **{ctx['sede']}** · Fecha y hora se registran automáticamente."
    )

    with st.form("asistencia_form", clear_on_submit=True):
        nombre = st.text_input(
            "Nombre del trabajador",
            placeholder="Ej: Juan Pérez",
            help="Escribe tu nombre completo.",
        )
        tipo = st.radio(
            "Tipo de registro",
            [TIPO_ENTRADA, TIPO_SALIDA],
            format_func=lambda t: _TIPO_LABELS[t],
            horizontal=True,
        )
        observaciones = st.text_area(
            "Observaciones (opcional)",
            placeholder="Agrega cualquier nota relevante…",
        )
        submitted = st.form_submit_button("💾 Guardar asistencia", use_container_width=True)

    if submitted:
        if not nombre.strip():
            st.error("El nombre del trabajador es obligatorio.")
        else:
            now = datetime.now()
            try:
                db.register_attendance(
                    trabajador=nombre.strip(),
                    tipo=tipo,
                    fecha=now.date(),
                    hora=now.time(),
                    sede=ctx["sede"],
                    observaciones=observaciones.strip() or None,
                    usuario_rol=ctx["usuario_rol"],
                )
            except Exception:  # noqa: BLE001
                st.error("No se pudo registrar la asistencia. Inténtalo nuevamente.")
            else:
                tipo_label = "Entrada" if tipo == TIPO_ENTRADA else "Salida"
                st.success(
                    f"✅ **{tipo_label}** registrada para **{nombre.strip()}** "
                    f"— {now.strftime('%H:%M')} del {now.strftime('%d/%m/%Y')}."
                )
                st.rerun()

    st.divider()
    st.subheader("Registros recientes")

    registros = db.list_attendance(sede=ctx["sede"], limit=50)
    if not registros:
        st.info("Aún no hay registros de asistencia para esta sede.")
        return

    rows = [
        {
            "Fecha": r["fecha"].strftime("%d/%m/%Y"),
            "Hora": str(r["hora"])[:5],
            "Trabajador": r["trabajador"],
            "Tipo": "Entrada" if r["tipo"] == TIPO_ENTRADA else "Salida",
            "Sede": r["sede"],
            "Observaciones": r["observaciones"] or "—",
        }
        for r in registros
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)
