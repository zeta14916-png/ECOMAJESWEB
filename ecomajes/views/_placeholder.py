"""Shared placeholder renderer used by every module view.

Renders a consistent "under construction" screen so the navigation structure can
be reviewed before any business logic exists.
"""

import streamlit as st


def render_placeholder(title: str, icon: str, description: str) -> None:
    st.header(f"{icon} {title}")
    st.caption(description)
    st.info("Módulo en construcción. La funcionalidad se implementará más adelante.")
