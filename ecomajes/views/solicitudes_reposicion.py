"""Solicitudes de Reposición view (GERENCIA).

Flujo oficial: Pendiente → Aprobada → Atendida | Rechazada

• Pendiente  — nueva solicitud creada desde Alertas.
• Aprobada   — Gerencia aprueba y define la cantidad; el stock se actualiza
               automáticamente y se registra un movimiento de Entrada.
• Atendida   — Gerencia confirma que la reposición ya fue recibida físicamente.
• Rechazada  — Gerencia rechaza e indica el motivo; el stock NO se modifica.

Reglas:
- Solo Gerencia puede operar este módulo.
- No se puede aprobar dos veces la misma solicitud.
- Al aprobar: stock anterior + cantidad aprobada = stock nuevo (auditado).
- Al rechazar: sin cambio de stock, motivo obligatorio.
- Al marcar atendida: solo cambia el estado, sin cambio de stock.
"""

from datetime import datetime

import streamlit as st

from ecomajes import config, db

_EMOJI = {
    db.REPO_PENDIENTE: "🟡",
    db.REPO_APROBADA: "🟢",
    db.REPO_ATENDIDA: "✅",
    db.REPO_RECHAZADA: "🔴",
}
_ALL_FILTER = "Todos"


def _label(estado: str) -> str:
    emoji = _EMOJI.get(estado, "")
    text = db.REPO_STATUS_LABELS.get(estado, estado)
    return f"{emoji} {text}"


def _num(value) -> float:
    return float(value) if value is not None else 0.0


def _fmt_dt(dt) -> str:
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d %H:%M")
    return str(dt) if dt else "—"


def _overview_table(requests: list[dict]) -> None:
    """Render the summary table with all required columns."""
    rows = []
    for r in requests:
        rows.append(
            {
                "N°": r["id"],
                "Fecha": _fmt_dt(r.get("created_at")),
                "Producto": r["descripcion"],
                "Código": r["codigo"] or "—",
                "Stock actual": _num(r["stock_actual"]),
                "Cant. solicitada": _num(r["cantidad_sugerida"]),
                "Cant. aprobada": _num(r.get("cantidad_aprobada")),
                "Motivo rechazo": r.get("motivo_rechazo") or "—",
                "Solicitado por": r["solicitado_por"],
                "Aprobado/Gestionado por": r.get("aprobado_por") or "—",
                "Sede": r["sede"],
                "Estado": _label(r["estado"]),
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _card_pendiente(r: dict, ctx: dict) -> None:
    """Actions available for a Pendiente request: Aprobar or Rechazar."""
    st.markdown(
        f"🟡 **Pendiente** · **{r['descripcion']}** `{r['codigo'] or '—'}` "
        f"· 📍 {r['sede']} · 👤 {r['solicitado_por']} · 🗓️ {_fmt_dt(r.get('created_at'))}"
    )
    col_ap, col_rj = st.columns(2)

    # ---- Aprobar ----
    with col_ap:
        with st.form(f"aprobar_{r['id']}"):
            st.write("**Aprobar reposición**")
            cant = st.number_input(
                "Cantidad a aprobar",
                min_value=0.01,
                value=float(_num(r["cantidad_sugerida"])) or 1.0,
                step=1.0,
                key=f"cant_{r['id']}",
            )
            if st.form_submit_button("✅ Aprobar", type="primary"):
                from decimal import Decimal
                try:
                    result = db.approve_replenishment_request(
                        request_id=r["id"],
                        cantidad_aprobada=Decimal(str(cant)),
                        usuario_rol=ctx["usuario_rol"],
                    )
                    db.log_audit(
                        db.AUDIT_MOVEMENT,
                        "Solicitudes de Reposición",
                        detalle=(
                            f"Aprobada solicitud #{r['id']} — "
                            f"{r['descripcion']} | "
                            f"Stock anterior: {result['stock_anterior']} → "
                            f"Stock nuevo: {result['stock_nuevo']}"
                        ),
                        usuario_rol=ctx["usuario_rol"],
                        sede=r["sede"],
                    )
                    st.success(
                        f"✅ Solicitud #{r['id']} aprobada. "
                        f"Stock actualizado: {result['stock_anterior']} → {result['stock_nuevo']}"
                    )
                except Exception as exc:  # noqa: BLE001
                    st.error(f"No se pudo aprobar: {exc}")
                else:
                    st.rerun()

    # ---- Rechazar ----
    with col_rj:
        with st.form(f"rechazar_{r['id']}"):
            st.write("**Rechazar reposición**")
            motivo = st.text_area(
                "Motivo del rechazo",
                placeholder="Indica el motivo…",
                key=f"motivo_{r['id']}",
            )
            if st.form_submit_button("🚫 Rechazar"):
                if not motivo.strip():
                    st.error("El motivo del rechazo es obligatorio.")
                else:
                    try:
                        db.reject_replenishment_request(
                            request_id=r["id"],
                            motivo=motivo.strip(),
                            usuario_rol=ctx["usuario_rol"],
                        )
                        db.log_audit(
                            "solicitud_rechazada",
                            "Solicitudes de Reposición",
                            detalle=(
                                f"Rechazada solicitud #{r['id']} — "
                                f"{r['descripcion']} | Motivo: {motivo.strip()}"
                            ),
                            usuario_rol=ctx["usuario_rol"],
                            sede=r["sede"],
                        )
                        st.success(f"🔴 Solicitud #{r['id']} rechazada.")
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"No se pudo rechazar: {exc}")
                    else:
                        st.rerun()


def _card_aprobada(r: dict, ctx: dict) -> None:
    """Actions available for an Aprobada request: Marcar como Atendida."""
    st.markdown(
        f"🟢 **Aprobada** · **{r['descripcion']}** `{r['codigo'] or '—'}` "
        f"· 📍 {r['sede']} · Aprobado por: {r.get('aprobado_por') or '—'} "
        f"· Cant. aprobada: **{_num(r.get('cantidad_aprobada'))}** "
        f"| Stock: {_num(r.get('stock_anterior'))} → {_num(r.get('stock_nuevo'))}"
    )
    if st.button(
        "📦 Marcar como Atendida",
        key=f"atender_{r['id']}",
        type="primary",
    ):
        try:
            db.attend_replenishment_request(
                request_id=r["id"],
                usuario_rol=ctx["usuario_rol"],
            )
            db.log_audit(
                "solicitud_atendida",
                "Solicitudes de Reposición",
                detalle=f"Atendida solicitud #{r['id']} — {r['descripcion']}",
                usuario_rol=ctx["usuario_rol"],
                sede=r["sede"],
            )
            st.success(f"✅ Solicitud #{r['id']} marcada como Atendida.")
        except Exception as exc:  # noqa: BLE001
            st.error(f"No se pudo marcar como atendida: {exc}")
        else:
            st.rerun()


def _card_terminal(r: dict) -> None:
    """Read-only display for terminal states (Atendida / Rechazada)."""
    estado = r["estado"]
    emoji = _EMOJI.get(estado, "")
    label = db.REPO_STATUS_LABELS.get(estado, estado)
    extra = ""
    if estado == db.REPO_RECHAZADA and r.get("motivo_rechazo"):
        extra = f" · Motivo: _{r['motivo_rechazo']}_"
    elif estado == db.REPO_ATENDIDA and r.get("stock_nuevo") is not None:
        extra = (
            f" · Cant. aprobada: **{_num(r.get('cantidad_aprobada'))}** "
            f"| Stock: {_num(r.get('stock_anterior'))} → {_num(r.get('stock_nuevo'))}"
        )
    st.markdown(
        f"{emoji} **{label}** · {r['descripcion']} `{r['codigo'] or '—'}` "
        f"· 📍 {r['sede']}{extra}"
    )


def render(ctx: dict) -> None:
    st.header(ctx["title"])
    st.caption(ctx["breadcrumb"])

    if ctx["usuario_rol"] != config.ROLE_GERENCIA:
        st.error("Esta sección es exclusiva de GERENCIA.")
        return

    # ---- Filtro de estado ----
    filter_options = [_ALL_FILTER] + list(db.REPO_STATUS_LABELS.keys())
    chosen = st.selectbox(
        "Filtrar por estado",
        filter_options,
        format_func=lambda k: "Todos" if k == _ALL_FILTER else _label(k),
        key="repo_estado_filter",
    )
    estado_filter = None if chosen == _ALL_FILTER else chosen
    requests = db.list_replenishment_requests(estado=estado_filter)

    if not requests:
        st.info("No hay solicitudes de reposición para el filtro seleccionado.")
        return

    # ---- Tabla resumen ----
    st.subheader("📋 Resumen de solicitudes")
    _overview_table(requests)

    # ---- Métricas rápidas ----
    total = len(requests)
    pendientes = sum(1 for r in requests if r["estado"] == db.REPO_PENDIENTE)
    aprobadas = sum(1 for r in requests if r["estado"] == db.REPO_APROBADA)
    m1, m2, m3 = st.columns(3)
    m1.metric("Total", total)
    m2.metric("🟡 Pendientes", pendientes)
    m3.metric("🟢 Aprobadas (por atender)", aprobadas)

    st.divider()
    st.subheader("⚙️ Gestionar solicitudes")

    # Show only the requests that need action (Pendiente / Aprobada) first,
    # then the terminal ones collapsed.
    activas = [r for r in requests if r["estado"] in (db.REPO_PENDIENTE, db.REPO_APROBADA)]
    terminadas = [r for r in requests if r["estado"] in (db.REPO_ATENDIDA, db.REPO_RECHAZADA)]

    for r in activas:
        with st.container(border=True):
            if r["estado"] == db.REPO_PENDIENTE:
                _card_pendiente(r, ctx)
            else:
                _card_aprobada(r, ctx)

    if terminadas:
        with st.expander(f"Historial — {len(terminadas)} solicitudes cerradas"):
            for r in terminadas:
                with st.container(border=False):
                    _card_terminal(r)
                    st.divider()
