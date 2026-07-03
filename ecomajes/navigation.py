"""Navigation and routing for ECOMAJES ERP.

Builds the sidebar menu based on the logged-in role + sede and dispatches to the
selected module view. The mapping from module key to render function lives here
so that `config` stays free of imports and circular dependencies are avoided.
"""

import streamlit as st

from ecomajes import config, session
from ecomajes.views import (
    alertas,
    comentarios,
    historial,
    inventario,
    material_nuevo,
    material_segundo_uso,
)

# Map each module key to its render function.
_RENDERERS = {
    config.INVENTARIO: inventario.render,
    config.ALERTAS: alertas.render,
    config.HISTORIAL: historial.render,
    config.COMENTARIOS: comentarios.render,
    config.MATERIAL_NUEVO: material_nuevo.render,
    config.MATERIAL_SEGUNDO_USO: material_segundo_uso.render,
}


def _render_sidebar(available: list[str]) -> None:
    """Render the sidebar: session info, module menu and logout."""
    with st.sidebar:
        st.title("ECOMAJES ERP")
        st.caption("Acero y Ferretería")
        st.divider()

        st.markdown(f"**Rol:** {session.current_role()}")
        st.markdown(f"**Sede:** {session.current_sede()}")
        st.divider()

        st.subheader("Módulos")
        for module_key in available:
            meta = config.MODULES[module_key]
            label = f"{meta['icon']} {meta['label']}"
            if st.button(label, key=f"nav_{module_key}", use_container_width=True):
                session.set_active_module(module_key)

        st.divider()
        if st.button("🚪 Cerrar sesión", use_container_width=True):
            session.logout()
            st.rerun()


def render_app() -> None:
    """Render the authenticated application: sidebar + active module view."""
    role = session.current_role()
    sede = session.current_sede()
    available = config.get_available_modules(role, sede)

    _render_sidebar(available)

    active = session.active_module()

    # Default to the first available module, or an empty-state message.
    if active not in available:
        if available:
            active = available[0]
            session.set_active_module(active)
        else:
            st.header("Sin módulos disponibles")
            st.info("Este rol/sede no tiene módulos asignados.")
            return

    _RENDERERS[active]()
