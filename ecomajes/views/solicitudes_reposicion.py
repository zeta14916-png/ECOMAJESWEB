"""Solicitudes de Reposición view (GERENCIA).

Lists every replenishment (purchase) request created from the ALERTAS module and
lets GERENCIA move each one through its lifecycle
(Pendiente → En proceso → Comprado → Recibido). This module ONLY manages the
purchase requests; it never changes inventory quantities.
"""

import streamlit as st

from ecomajes import config, db

_STATUS_KEYS = list(db.REPO_STATUS_LABELS.keys())
_STATUS_EMOJI = {
    db.REPO_PENDIENTE: "🟡",
    db.REPO_EN_PROCESO: "🔵",
    db.REPO_COMPRADO: "🟠",
    db.REPO_RECIBIDO: "🟢",
}


def _status_label(key: str) -> str:
    return db.REPO_STATUS_LABELS.get(key, key)


def _num(value) -> float:
    return float(value) if value is not None else 0.0


def _overview_table(requests: list[dict]) -> None:
    rows = [
        {
            "Fecha": r["created_at"].strftime("%Y-%m-%d %H:%M"),
            "Producto": r["descripcion"],
            "Código": r["codigo"] or "—",
            "Sede": r["sede"],
            "Stock actual": _num(r["stock_actual"]),
            "Stock mínimo": _num(r["stock_minimo"]),
            "Cantidad sugerida": _num(r["cantidad_sugerida"]),
            "Solicitado por": r["solicitado_por"],
            "Estado": _status_label(r["estado"]),
        }
        for r in requests
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _status_editor(r: dict) -> None:
    emoji = _STATUS_EMOJI.get(r["estado"], "")
    with st.container(border=True):
        st.markdown(
            f"{emoji} **{r['descripcion']}** ({r['codigo'] or '—'}) · "
            f"📍 {r['sede']} · 👤 {r['solicitado_por']} · "
            f"🗓️ {r['created_at'].strftime('%Y-%m-%d %H:%M')}"
        )
        current = r["estado"] if r["estado"] in _STATUS_KEYS else db.REPO_PENDIENTE
        cols = st.columns([2, 1])
        with cols[0]:
            nuevo = st.selectbox(
                "Estado",
                _STATUS_KEYS,
                index=_STATUS_KEYS.index(current),
                format_func=_status_label,
                key=f"repo_estado_{r['id']}",
            )
        with cols[1]:
            st.write("")
            st.write("")
            if st.button("Actualizar estado", key=f"repo_upd_{r['id']}"):
                db.set_replenishment_status(r["id"], nuevo)
                st.success("Estado actualizado.")
                st.rerun()


def render(ctx: dict) -> None:
    st.header(ctx["title"])
    st.caption(ctx["breadcrumb"])

    if ctx["usuario_rol"] != config.ROLE_GERENCIA:
        st.error("Esta sección es exclusiva de GERENCIA.")
        return

    estado = st.selectbox(
        "Filtrar por estado",
        [None, *_STATUS_KEYS],
        format_func=lambda k: "Todos" if k is None else _status_label(k),
        key="repo_estado_filter",
    )
    requests = db.list_replenishment_requests(estado=estado)

    if not requests:
        st.info("No hay solicitudes de reposición para el filtro seleccionado.")
        return

    st.subheader("Solicitudes")
    _overview_table(requests)

    st.divider()
    st.subheader("Actualizar estado")
    for r in requests:
        _status_editor(r)
