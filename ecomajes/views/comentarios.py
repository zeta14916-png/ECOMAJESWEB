"""Comentarios view for ECOMAJES ERP.

Any role can leave a comment (a question, issue or note). Each comment records
the date, the author's role (the app logs in by role, so "usuario" = role),
the location/scope it was written under, the text and a status
(Pendiente / En revisión / Atendido).

OPERARIOS additionally must enter their name (trabajador) since they log in
without an individual account.

GERENCIA additionally can respond to a comment and change its status. Other
roles see the read-only history plus the response, if any.
"""

import streamlit as st

from ecomajes import config, db

_STATUS_KEYS = list(db.COMMENT_STATUS_LABELS.keys())
_STATUS_EMOJI = {
    db.COMMENT_PENDIENTE: "🟡",
    db.COMMENT_EN_REVISION: "🔵",
    db.COMMENT_ATENDIDO: "🟢",
}


def _status_label(key: str) -> str:
    return db.COMMENT_STATUS_LABELS.get(key, key)


def _new_comment_form(ctx: dict) -> None:
    es_operario = ctx["usuario_rol"] == config.ROLE_OPERARIOS
    with st.expander("➕ Escribir un comentario", expanded=True):
        with st.form("new_comment_form", clear_on_submit=True):
            # OPERARIOS ingresa su nombre porque no tienen cuenta individual.
            if es_operario:
                trabajador = st.text_input(
                    "Tu nombre",
                    placeholder="Ej: Juan Pérez",
                    help="Escribe tu nombre completo.",
                )
            tipo_label = st.selectbox(
                "Tipo",
                ["Comentario", "Sugerencia", "Observación"],
            )
            texto = st.text_area(
                tipo_label,
                placeholder=f"Escribe tu {tipo_label.lower()}…",
            )
            submitted = st.form_submit_button("Enviar", use_container_width=True)

        if submitted:
            if es_operario and not trabajador.strip():
                st.error("Debes ingresar tu nombre.")
                return
            if not texto.strip():
                st.error(f"El {tipo_label.lower()} no puede estar vacío.")
                return
            comentario_final = f"[{tipo_label}] {texto.strip()}"
            try:
                db.add_comment(
                    usuario_rol=ctx["usuario_rol"],
                    sede=ctx.get("sede"),
                    comentario=comentario_final,
                    trabajador=trabajador.strip() if es_operario else None,
                )
            except Exception as exc:  # noqa: BLE001
                st.error(f"No se pudo guardar el comentario: {exc}")
            else:
                st.success("Comentario enviado.")
                st.rerun()


def _filters() -> str | None:
    options = [None, *_STATUS_KEYS]
    return st.selectbox(
        "Filtrar por estado",
        options,
        format_func=lambda k: "Todos" if k is None else _status_label(k),
        key="comentarios_estado_filter",
    )


def _gerencia_controls(c: dict) -> None:
    """Response + status controls, shown only to GERENCIA."""
    col1, col2 = st.columns([2, 1])
    with col1:
        with st.form(f"respond_form_{c['id']}"):
            respuesta = st.text_area(
                "Respuesta de gerencia",
                value=c["respuesta"] or "",
                key=f"resp_txt_{c['id']}",
            )
            if st.form_submit_button("💬 Guardar respuesta"):
                if not respuesta.strip():
                    st.error("La respuesta no puede estar vacía.")
                else:
                    db.respond_comment(
                        c["id"], respuesta.strip(), config.ROLE_GERENCIA
                    )
                    st.success("Respuesta guardada.")
                    st.rerun()
    with col2:
        current = (
            c["estado"] if c["estado"] in _STATUS_KEYS else db.COMMENT_PENDIENTE
        )
        nuevo = st.selectbox(
            "Estado",
            _STATUS_KEYS,
            index=_STATUS_KEYS.index(current),
            format_func=_status_label,
            key=f"estado_sel_{c['id']}",
        )
        if st.button("Actualizar estado", key=f"estado_btn_{c['id']}"):
            db.set_comment_status(c["id"], nuevo)
            st.success("Estado actualizado.")
            st.rerun()


def _render_comment(c: dict, is_gerencia: bool) -> None:
    emoji = _STATUS_EMOJI.get(c["estado"], "")
    fecha = c["created_at"].strftime("%Y-%m-%d %H:%M")
    ambito = c["sede"] or "—"
    autor = c.get("trabajador") or c["usuario_rol"]
    with st.container(border=True):
        st.markdown(
            f"{emoji} **{_status_label(c['estado'])}** · "
            f"🗓️ {fecha} · 👤 {autor} · 📍 {ambito}"
        )
        st.write(c["comentario"])
        if c["respuesta"]:
            respondido = (
                c["respondido_at"].strftime("%Y-%m-%d %H:%M")
                if c["respondido_at"]
                else ""
            )
            st.info(
                f"**Respuesta de {c['respondido_por'] or 'Gerencia'}** "
                f"({respondido}):\n\n{c['respuesta']}"
            )
        if is_gerencia:
            _gerencia_controls(c)


def render(ctx: dict) -> None:
    st.header(ctx["title"])
    st.caption(ctx["breadcrumb"])

    is_gerencia = ctx["usuario_rol"] == config.ROLE_GERENCIA

    _new_comment_form(ctx)
    st.divider()

    estado = _filters()
    comentarios = db.list_comments(estado=estado)

    st.subheader("Comentarios")
    if not comentarios:
        st.caption("No hay comentarios para el filtro seleccionado.")
        return
    for c in comentarios:
        _render_comment(c, is_gerencia)
