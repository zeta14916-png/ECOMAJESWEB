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


def requires_username(role: str) -> bool:
    """Return True if the given role must supply a username to log in."""
    return role in (config.ROLE_ADMINISTRATIVA, config.ROLE_GERENCIA)


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


def find_employee_by_username(username: str, role: str) -> dict | None:
    """Busca un empleado activo por username y rol.

    Retorna el dict del empleado (con 'nombre', 'username', 'rol') si existe
    y está activo. Retorna None si no hay coincidencia o si la DB no está
    disponible (para mantener compatibilidad en entornos sin empleados).
    """
    try:
        from ecomajes import db
        employees = db.list_employees(search=username.strip())
        for emp in employees:
            if (
                emp.get("username", "").lower() == username.strip().lower()
                and emp.get("rol") == role
                and emp.get("estado") == db.EMPLOYEE_ACTIVO
            ):
                return emp
        return None
    except Exception:
        return None


def validate_login(role: str, username: str, password: str) -> tuple[bool, dict | None]:
    """Valida el inicio de sesión completo.

    Retorna (ok, employee_dict_or_None).
    - Para OPERARIOS: solo verifica que no se requiere contraseña → siempre True.
    - Para ADMINISTRATIVA/GERENCIA:
        1. Verifica que el username no esté vacío.
        2. Busca el empleado por username+rol en la DB.
        3. Si se encuentra → valida contraseña contra la DB (hash).
        4. Si no se encuentra en DB → valida contraseña contra env var (fallback).
    """
    if not requires_password(role):
        return True, None

    if not username.strip():
        return False, None

    # Intentar validar contra la tabla de empleados primero.
    emp = find_employee_by_username(username.strip(), role)
    if emp is not None:
        # Empleado encontrado: validar contraseña contra su hash en DB.
        try:
            from ecomajes import db
            ok = db.verify_employee_password(emp["id"], password)
        except Exception:
            ok = False
        if ok:
            return True, emp
        # Si la contraseña del empleado falla, intentar env var como fallback
        # (útil cuando el admin cambia la clave env pero no la del empleado).
        if verify_password(role, password):
            return True, emp
        return False, None

    # Empleado no encontrado en DB: usar fallback de env var.
    # El usuario se registra con el username proporcionado.
    if verify_password(role, password):
        return True, None
    return False, None
