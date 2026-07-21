"""Shared placeholder renderer used by every navigation page.

Renders a consistent "under construction" screen so the navigation structure can
be reviewed before any business logic exists.
"""

import streamlit as st


def render_page(title: str, breadcrumb: str) -> None:
    st.header(title)
    st.caption(breadcrumb)
    st.info("Página en construcción. La funcionalidad se implementará más adelante.")
