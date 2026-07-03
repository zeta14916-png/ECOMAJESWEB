"""Session state helpers for ECOMAJES ERP.

Thin wrappers around st.session_state so the rest of the app never touches raw
keys directly. Keeps login/logout state and the active page in one place.
"""

import streamlit as st

# Session state keys
KEY_ROLE = "role"
KEY_SEDE = "sede"
KEY_AUTHENTICATED = "authenticated"
KEY_ACTIVE_PAGE = "active_page"


def init_state() -> None:
    """Ensure all expected keys exist in the session state."""
    st.session_state.setdefault(KEY_ROLE, None)
    st.session_state.setdefault(KEY_SEDE, None)
    st.session_state.setdefault(KEY_AUTHENTICATED, False)
    st.session_state.setdefault(KEY_ACTIVE_PAGE, None)


def is_authenticated() -> bool:
    """Return True when a user has completed the login flow."""
    return bool(st.session_state.get(KEY_AUTHENTICATED))


def login(role: str, sede: str) -> None:
    """Store the authenticated session for a role + sede."""
    st.session_state[KEY_ROLE] = role
    st.session_state[KEY_SEDE] = sede
    st.session_state[KEY_AUTHENTICATED] = True
    st.session_state[KEY_ACTIVE_PAGE] = None


def logout() -> None:
    """Clear the session and return to the login screen."""
    st.session_state[KEY_ROLE] = None
    st.session_state[KEY_SEDE] = None
    st.session_state[KEY_AUTHENTICATED] = False
    st.session_state[KEY_ACTIVE_PAGE] = None


def current_role() -> str | None:
    return st.session_state.get(KEY_ROLE)


def current_sede() -> str | None:
    return st.session_state.get(KEY_SEDE)


def active_page() -> str | None:
    return st.session_state.get(KEY_ACTIVE_PAGE)


def set_active_page(page_key: str) -> None:
    st.session_state[KEY_ACTIVE_PAGE] = page_key
