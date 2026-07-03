"""Navigation and routing for ECOMAJES ERP.

Builds the sidebar menu (flat pages and grouped pages) based on the logged-in
role + sede and dispatches to the selected page. Every page currently renders a
shared placeholder — business logic is added later, one module at a time.
"""

import streamlit as st

from ecomajes import config, session
from ecomajes.views import _placeholder


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
        st.markdown(f"**Sede:** {session.current_sede()}")
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
    _placeholder.render_page(page.label, _breadcrumb(role, sede, group_label))
