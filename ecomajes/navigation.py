"""Navigation and routing for ECOMAJES ERP.

Builds the sidebar menu (flat pages and grouped pages) based on the logged-in
role + sede and dispatches to the selected page. Pages listed in ROUTES render a
real module view; every other page renders the shared placeholder.
"""

import streamlit as st

from ecomajes import config, db, session
from ecomajes.views import (
    _placeholder,
    balance,
    gestion_inventario,
    inventario,
    movimientos,
    precios,
    productos,
    recursos_humanos,
    reporte_ventas,
    reportes,
)

# --------------------------------------------------------------------------- #
# Routing table: page key -> which real view to render and with what scope.
# Any page not listed here falls back to the placeholder.
# --------------------------------------------------------------------------- #
ROUTES = {
    # OPERARIOS — read-only inventory for the chosen sede.
    "op_inventario": {"view": "inventario", "material_tipo": None, "editable": False},
    # ÁREA ADMINISTRATIVA — Material Nuevo.
    "adm_mn_inventario": {
        "view": "inventario",
        "material_tipo": db.TIPO_NUEVO,
        "editable": True,
    },
    "adm_mn_entrada_movimientos": {
        "view": "movimientos",
        "material_tipo": db.TIPO_NUEVO,
        "editable": True,
    },
    "adm_mn_reporte_ventas": {
        "view": "reporte_ventas",
        "material_tipo": None,
        "editable": True,
    },
    # ÁREA ADMINISTRATIVA — Material Segundo Uso.
    "adm_msu_inventario": {
        "view": "inventario",
        "material_tipo": db.TIPO_SEGUNDO_USO,
        "editable": True,
    },
    "adm_msu_registrar_producto": {
        "view": "inventario",
        "material_tipo": db.TIPO_SEGUNDO_USO,
        "editable": True,
        "focus_add": True,
    },
    "adm_msu_registrar_movimientos": {
        "view": "movimientos",
        "material_tipo": db.TIPO_SEGUNDO_USO,
        "editable": True,
    },
    # GERENCIA — consolidated inventory overview (combined across sedes).
    "ger_gestion_inventario": {
        "view": "gestion_inventario",
        "material_tipo": None,
        "editable": True,
    },
    # GERENCIA — price list (all material types).
    "ger_precios": {
        "view": "precios",
        "material_tipo": None,
        "editable": True,
    },
    # GERENCIA — financial balance + dashboard.
    "ger_balance_financiero": {
        "view": "balance",
        "material_tipo": None,
        "editable": True,
    },
    # GERENCIA — product catalog (all sedes when Empresa Completa).
    "ger_productos": {
        "view": "productos",
        "material_tipo": None,
        "editable": True,
    },
    # GERENCIA — Recursos Humanos (employees + payroll).
    "ger_recursos_humanos": {
        "view": "recursos_humanos",
        "material_tipo": None,
        "editable": True,
    },
    # GERENCIA — period-based reports (all sedes when Empresa Completa).
    "ger_reportes": {
        "view": "reportes",
        "material_tipo": None,
        "editable": True,
    },
}

_VIEWS = {
    "inventario": inventario.render,
    "gestion_inventario": gestion_inventario.render,
    "movimientos": movimientos.render,
    "precios": precios.render,
    "reporte_ventas": reporte_ventas.render,
    "balance": balance.render,
    "productos": productos.render,
    "recursos_humanos": recursos_humanos.render,
    "reportes": reportes.render,
}


def _iter_pages(nav: list):
    """Yield (page, group_label_or_None) for every page in a nav tree."""
    for item in nav:
        if isinstance(item, config.Group):
            for page in item.pages:
                yield page, item.label
        else:  # config.Page
            yield item, None


def _page_index(nav: list) -> dict:
    """Map page key -> (Page, group_label_or_None)."""
    return {page.key: (page, group) for page, group in _iter_pages(nav)}


def _render_sidebar(nav: list) -> None:
    """Render the sidebar: session info, menu (flat + grouped) and logout."""
    with st.sidebar:
        st.title("ECOMAJES ERP")
        st.caption("Acero y Ferretería")
        st.divider()

        st.markdown(f"**Rol:** {session.current_role()}")
        scope_label = (
            "Ámbito"
            if session.current_role() == config.ROLE_GERENCIA
            else "Sede"
        )
        st.markdown(f"**{scope_label}:** {session.current_sede()}")
        st.divider()

        for item in nav:
            if isinstance(item, config.Group):
                with st.expander(f"{item.icon} {item.label}", expanded=True):
                    for page in item.pages:
                        if st.button(
                            page.label,
                            key=f"nav_{page.key}",
                            use_container_width=True,
                        ):
                            session.set_active_page(page.key)
            else:  # config.Page
                if st.button(
                    item.label,
                    key=f"nav_{item.key}",
                    use_container_width=True,
                ):
                    session.set_active_page(item.key)

        st.divider()
        if st.button("🚪 Cerrar sesión", use_container_width=True):
            session.logout()
            st.rerun()


def _breadcrumb(role: str, sede: str, group_label: str | None) -> str:
    parts = [role, sede]
    if group_label:
        parts.append(group_label)
    return " · ".join(parts)


def _build_context(page, group_label, role, sede, route) -> dict:
    """Assemble the context dict passed to a real view."""
    include_all = sede == config.SEDE_EMPRESA_COMPLETA
    return {
        "title": page.label,
        "breadcrumb": _breadcrumb(role, sede, group_label),
        "sede": sede,
        "material_tipo": route.get("material_tipo"),
        "include_all_sedes": include_all,
        "editable": route.get("editable", False),
        "focus_add": route.get("focus_add", False),
        "usuario_rol": role,
        "sede_options": [config.SEDE_PRINCIPAL, config.SEDE_SUCURSAL],
    }


def render_app() -> None:
    """Render the authenticated application: sidebar + active page."""
    role = session.current_role()
    sede = session.current_sede()
    nav = config.get_navigation(role, sede)
    index = _page_index(nav)

    _render_sidebar(nav)

    active = session.active_page()

    # Default to the first available page, or an empty-state message.
    if active not in index:
        if index:
            active = next(iter(index))
            session.set_active_page(active)
        else:
            st.header("Sin páginas disponibles")
            st.info("Este rol/sede no tiene páginas asignadas.")
            return

    page, group_label = index[active]
    route = ROUTES.get(page.key)

    if route:
        ctx = _build_context(page, group_label, role, sede, route)
        _VIEWS[route["view"]](ctx)
    else:
        _placeholder.render_page(page.label, _breadcrumb(role, sede, group_label))
