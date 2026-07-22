"""Authentication helpers for ECOMAJES ERP.

Handles the password requirements per role. Passwords are read from environment
variables so no secret is hard-coded in the source. Development fallbacks are
provided so the scaffold runs out of the box; replace them with real secrets
before going to production.

No business logic beyond role gating lives here.
"""

import os

from ecomajes import config

# Environment variable names used to configure passwords.
ENV_ADMIN_PASSWORD = "ECOMAJES_ADMIN_PASSWORD"
ENV_GERENCIA_PASSWORD = "ECOMAJES_GERENCIA_PASSWORD"

# Development-only fallbacks. Override via environment variables / secrets.
_DEV_ADMIN_PASSWORD = "admin"
_DEV_GERENCIA_PASSWORD = "gerencia"


def requires_password(role: str) -> bool:
    """Return True if the given role must supply a password to log in."""
    return config.ROLE_REQUIRES_PASSWORD.get(role, False)


def _expected_password(role: str) -> str | None:
    """Return the configured password for a role, or None if not applicable."""
    if role == config.ROLE_ADMINISTRATIVA:
        return os.environ.get(ENV_ADMIN_PASSWORD, _DEV_ADMIN_PASSWORD)
    if role == config.ROLE_GERENCIA:
        return os.environ.get(ENV_GERENCIA_PASSWORD, _DEV_GERENCIA_PASSWORD)
    return None


def verify_password(role: str, password: str) -> bool:
    """Verify a submitted password for a role.

    Roles that do not require a password always pass. Roles that do require one
    are compared against the configured value.
    """
    if not requires_password(role):
        return True
    expected = _expected_password(role)
    if not expected:
        return False
    return password == expected
