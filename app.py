"""ECOMAJES ERP — application entry point.

Steel & hardware company ERP. This file only wires together the architecture:
session initialization, the login gate, and the authenticated navigation. All
module business logic is implemented in `ecomajes/views/` and is intentionally
left as placeholders until each module is approved.
"""

import streamlit as st

from ecomajes import login, navigation, session

st.set_page_config(page_title="ECOMAJES ERP", page_icon="🔩", layout="wide")


def main() -> None:
    session.init_state()

    if session.is_authenticated():
        navigation.render_app()
    else:
        login.render_login()


if __name__ == "__main__":
    main()
