"""Central configuration for ECOMAJES ERP.

Defines roles, sedes (locations), modules and the access matrix that maps each
role + sede combination to the set of modules it is allowed to see.

This file holds NO business logic. It only describes the structure of the app.
"""

# --------------------------------------------------------------------------- #
# Roles
# --------------------------------------------------------------------------- #
ROLE_OPERARIOS = "OPERARIOS"
ROLE_ADMINISTRATIVA = "ÁREA ADMINISTRATIVA"
ROLE_GERENCIA = "GERENCIA"

ROLES = [ROLE_OPERARIOS, ROLE_ADMINISTRATIVA, ROLE_GERENCIA]

# Which roles require a password to enter.
ROLE_REQUIRES_PASSWORD = {
    ROLE_OPERARIOS: False,
    ROLE_ADMINISTRATIVA: True,
    ROLE_GERENCIA: True,
}

# --------------------------------------------------------------------------- #
# Sedes (locations)
# --------------------------------------------------------------------------- #
SEDE_PRINCIPAL = "Sede Principal"
SEDE_SUCURSAL = "Sucursal"

SEDES = [SEDE_PRINCIPAL, SEDE_SUCURSAL]

# --------------------------------------------------------------------------- #
# Modules
# --------------------------------------------------------------------------- #
INVENTARIO = "inventario"
ALERTAS = "alertas"
HISTORIAL = "historial"
COMENTARIOS = "comentarios"
MATERIAL_NUEVO = "material_nuevo"
MATERIAL_SEGUNDO_USO = "material_segundo_uso"

# Metadata used to render menu entries. `label` is shown to the user, `icon`
# is a small emoji marker for the sidebar.
MODULES = {
    INVENTARIO: {"label": "Inventario", "icon": "📦"},
    ALERTAS: {"label": "Alertas", "icon": "🔔"},
    HISTORIAL: {"label": "Historial", "icon": "🕓"},
    COMENTARIOS: {"label": "Comentarios", "icon": "💬"},
    MATERIAL_NUEVO: {"label": "Material Nuevo", "icon": "🆕"},
    MATERIAL_SEGUNDO_USO: {"label": "Material Segundo Uso", "icon": "♻️"},
}

# --------------------------------------------------------------------------- #
# Access matrix
# --------------------------------------------------------------------------- #
# Modules available to OPERARIOS (same for every sede).
_OPERARIOS_MODULES = [INVENTARIO, ALERTAS, HISTORIAL, COMENTARIOS]

# Modules available to ÁREA ADMINISTRATIVA, which depend on the chosen sede.
_ADMINISTRATIVA_MODULES = {
    SEDE_PRINCIPAL: [MATERIAL_NUEVO, MATERIAL_SEGUNDO_USO],
    SEDE_SUCURSAL: [MATERIAL_NUEVO],
}

# GERENCIA can access every module regardless of sede.
_GERENCIA_MODULES = [
    INVENTARIO,
    ALERTAS,
    HISTORIAL,
    COMENTARIOS,
    MATERIAL_NUEVO,
    MATERIAL_SEGUNDO_USO,
]


def get_available_modules(role: str, sede: str) -> list[str]:
    """Return the ordered list of module keys allowed for a role + sede.

    Args:
        role: One of the ROLE_* constants.
        sede: One of the SEDE_* constants.

    Returns:
        List of module keys (subset of MODULES) the user may access.
    """
    if role == ROLE_OPERARIOS:
        return list(_OPERARIOS_MODULES)
    if role == ROLE_ADMINISTRATIVA:
        return list(_ADMINISTRATIVA_MODULES.get(sede, []))
    if role == ROLE_GERENCIA:
        return list(_GERENCIA_MODULES)
    return []
