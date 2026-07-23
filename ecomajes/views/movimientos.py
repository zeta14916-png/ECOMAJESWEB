"""Movement registration view for ECOMAJES ERP.

Registers stock movements (entrada / salida / venta) for a product. Each
movement atomically updates the product stock and is recorded for history.

Sales support several sale types (Unidad / Metro / Centímetro / Corte
personalizado). For the special sale types (metro / centímetro / corte
personalizado) the operator sees extra fields — cantidad vendida, precio
sugerido, precio final, autorizado por gerencia and observación — and the sale
is stored using the *precio final* so every report reflects the amount actually
charged. Plain unit sales keep their original automatic pricing.

Also shows the most recent movements for the current scope.
"""

from decimal import Decimal

import streamlit as st

from ecomajes import db

_TIPOS = [db.MOVEMENT_ENTRADA, db.MOVEMENT_SALIDA, db.MOVEMENT_VENTA]
_METODO_PAGO_OPTIONS = db.METODO_PAGO_OPTIONS

# Sale types exposed in this flow (per requirement: excludes plancha completa).
_VENTA_TIPOS = [
    db.VENTA_UNIDAD,
    db.VENTA_METRO,
    db.VENTA_CENTIMETRO,
    db.VENTA_CORTE_PERSONALIZADO,
]
# Sale types that use the special-price flow (manual precio final).
_SPECIAL_VENTA = {
    db.VENTA_METRO,
    db.VENTA_CENTIMETRO,
    db.VENTA_CORTE_PERSONALIZADO,
}

# Session-state keys cleared after a successful registration.
_INPUT_KEYS = (
    "mov_cant_simple",
    "mov_nota_simple",
    "mov_cant_venta",
    "mov_nota_unidad",
    "mov_precio_final",
    "mov_precio_ctx",
    "mov_autorizado",
    "mov_observacion",
    "mov_metodo_pago",
)


def _product_label(p: dict) -> str:
    tipo = db.TIPO_LABELS.get(p["material_tipo"], p["material_tipo"])
    return (
        f"{p['nombre']} · {tipo} · {p['sede']} · "
        f"stock: {float(p['stock'])} {p['unidad']}"
    )


def _suggested_unit_price(product_id: int) -> Decimal | None:
    """Configured suggested unit price for a product (read-only)."""
    price = db.get_price(product_id)
    if not price:
        return None
    return price.get("precio_sugerido") or price.get("precio")


def _flash() -> None:
    msg = st.session_state.pop("mov_flash", None)
    if msg:
        st.success(msg)


def _recent_movements(ctx: dict) -> None:
    st.subheader("Movimientos recientes")
    movements = db.list_movements(
        sede=ctx["sede"],
        material_tipo=ctx["material_tipo"],
        include_all_sedes=ctx["include_all_sedes"],
        limit=50,
    )
    if not movements:
        st.caption("Sin movimientos registrados.")
        return
    rows = [
        {
            "Fecha": m["created_at"].strftime("%Y-%m-%d %H:%M"),
            "Producto": m["producto"],
            "Sede": m["sede"],
            "Tipo": db.MOVEMENT_LABELS.get(m["tipo"], m["tipo"]),
            "Tipo venta": (
                db.TIPO_VENTA_LABELS.get(m["tipo_venta"], m["tipo_venta"])
                if m["tipo_venta"]
                else "—"
            ),
            "Método pago": (
                db.METODO_PAGO_LABELS.get(m.get("metodo_pago"), m.get("metodo_pago"))
                if m.get("metodo_pago")
                else "—"
            ),
            "Cantidad": float(m["cantidad"]),
            "Unidad": m["unidad"],
            "Precio unit.": (
                float(m["precio_unitario"])
                if m["precio_unitario"] is not None
                else None
            ),
            "Precio final": (
                float(m["precio_total"])
                if m["precio_total"] is not None
                else None
            ),
            "Autorizado por": m["autorizado_por"] or "—",
            "Observación": m["nota"] or "—",
        }
        for m in movements
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _register(
    ctx: dict,
    product: dict,
    tipo: str,
    cantidad: Decimal,
    *,
    nota: str | None = None,
    tipo_venta: str | None = None,
    precio_final: Decimal | None = None,
    autorizado_por: str | None = None,
    metodo_pago: str | None = None,
) -> None:
    """Perform the DB write, audit log, flash message and rerun."""
    try:
        new_stock = db.register_movement(
            product_id=product["id"],
            tipo=tipo,
            cantidad=cantidad,
            nota=nota,
            usuario_rol=ctx["usuario_rol"],
            sede=product["sede"],
            tipo_venta=tipo_venta,
            precio_final=precio_final,
            autorizado_por=autorizado_por,
            metodo_pago=metodo_pago,
        )
    except db.StockError as exc:
        st.error(str(exc))
        return
    except Exception as exc:  # noqa: BLE001
        st.error(f"No se pudo registrar el movimiento: {exc}")
        return

    detalle = f"{db.MOVEMENT_LABELS.get(tipo, tipo)} · {product['nombre']} · "
    detalle += f"{float(cantidad)} {product['unidad']}"
    if tipo_venta:
        detalle += f" · {db.TIPO_VENTA_LABELS.get(tipo_venta, tipo_venta)}"
    db.log_audit(
        db.AUDIT_MOVEMENT,
        "Movimientos",
        detalle=detalle,
        usuario_rol=ctx["usuario_rol"],
        sede=product["sede"],
    )
    for key in _INPUT_KEYS:
        st.session_state.pop(key, None)
    st.session_state["mov_flash"] = (
        f"Movimiento registrado. Nuevo stock de «{product['nombre']}»: "
        f"{float(new_stock)} {product['unidad']}."
    )
    st.rerun()


def _render_simple(ctx: dict, product: dict, tipo: str) -> None:
    """Entrada / Salida: quantity + optional note."""
    cantidad = st.number_input(
        "Cantidad", min_value=0.001, value=1.0, step=1.0, key="mov_cant_simple"
    )
    nota = st.text_input("Nota (opcional)", key="mov_nota_simple")
    if st.button("Registrar movimiento", key="mov_submit_simple"):
        _register(
            ctx, product, tipo, Decimal(str(cantidad)),
            nota=nota.strip() or None,
        )


def _render_venta(ctx: dict, product: dict) -> None:
    tipo_venta = st.selectbox(
        "Tipo de venta",
        _VENTA_TIPOS,
        format_func=lambda t: db.TIPO_VENTA_LABELS[t],
        key="mov_tipo_venta",
    )
    cantidad = st.number_input(
        "Cantidad vendida",
        min_value=0.001,
        value=1.0,
        step=1.0,
        key="mov_cant_venta",
    )
    cantidad_dec = Decimal(str(cantidad))

    # Método de pago — obligatorio para toda venta.
    metodo_pago = st.selectbox(
        "Método de pago *",
        [None, *_METODO_PAGO_OPTIONS],
        format_func=lambda m: "— Seleccionar —" if m is None else db.METODO_PAGO_LABELS[m],
        key="mov_metodo_pago",
    )

    if tipo_venta not in _SPECIAL_VENTA:
        # Unit sale — keep the original automatic pricing (precio from prices).
        nota = st.text_input("Nota (opcional)", key="mov_nota_unidad")
        if st.button("Registrar venta", key="mov_submit_unidad"):
            if metodo_pago is None:
                st.error("Debes seleccionar un método de pago.")
                return
            _register(
                ctx, product, db.MOVEMENT_VENTA, cantidad_dec,
                nota=nota.strip() or None,
                tipo_venta=db.VENTA_UNIDAD,
                metodo_pago=metodo_pago,
            )
        return

    # Special sale — manual precio final + authorisation + observación.
    unit_price = _suggested_unit_price(product["id"])
    sugerido_total = (
        unit_price * cantidad_dec if unit_price is not None else Decimal("0")
    )

    st.number_input(
        "Precio sugerido",
        value=float(sugerido_total),
        disabled=True,
        help="Precio sugerido = precio configurado × cantidad. Referencia.",
    )
    # Default precio final to the suggested total, but preserve manual edits
    # while product / sale type / quantity stay the same. When any of those
    # change, re-sync the default to the freshly computed suggested price.
    ctx_sig = (product["id"], tipo_venta, float(cantidad_dec))
    if st.session_state.get("mov_precio_ctx") != ctx_sig:
        st.session_state["mov_precio_ctx"] = ctx_sig
        st.session_state["mov_precio_final"] = float(sugerido_total)
    precio_final = st.number_input(
        "Precio final", min_value=0.0, step=0.01, key="mov_precio_final"
    )
    autorizado = st.text_input(
        "Autorizado por Gerencia", key="mov_autorizado"
    )
    corte = tipo_venta == db.VENTA_CORTE_PERSONALIZADO
    observacion = st.text_area(
        "Observación" + (" (obligatoria)" if corte else ""),
        key="mov_observacion",
    )

    if st.button("Registrar venta", key="mov_submit_especial"):
        if metodo_pago is None:
            st.error("Debes seleccionar un método de pago.")
            return
        if corte and not observacion.strip():
            st.error("La observación es obligatoria para Corte personalizado.")
            return
        _register(
            ctx, product, db.MOVEMENT_VENTA, cantidad_dec,
            nota=observacion.strip() or None,
            tipo_venta=tipo_venta,
            precio_final=Decimal(str(precio_final)),
            autorizado_por=autorizado.strip() or None,
            metodo_pago=metodo_pago,
        )


def render(ctx: dict) -> None:
    st.header(ctx["title"])
    st.caption(ctx["breadcrumb"])
    _flash()

    products = db.list_products(
        sede=ctx["sede"],
        material_tipo=ctx["material_tipo"],
        include_all_sedes=ctx["include_all_sedes"],
    )
    if not products:
        st.info("Primero registra productos en el módulo de Inventario.")
        return

    options = {p["id"]: p for p in products}
    product_id = st.selectbox(
        "Producto",
        list(options.keys()),
        format_func=lambda pid: _product_label(options[pid]),
        key="mov_producto",
    )
    product = options[product_id]

    tipo = st.selectbox(
        "Tipo de movimiento",
        _TIPOS,
        format_func=lambda t: db.MOVEMENT_LABELS[t],
        key="mov_tipo",
    )

    if tipo == db.MOVEMENT_VENTA:
        _render_venta(ctx, product)
    else:
        _render_simple(ctx, product, tipo)

    st.divider()
    _recent_movements(ctx)
