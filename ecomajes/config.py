"""Central configuration for ECOMAJES ERP.

Defines roles, sedes (locations) and the navigation tree that maps each role +
sede combination to its menu structure. Menus may be flat (a list of pages) or
grouped (a labelled group containing sub-pages).

This file holds NO business logic. It only describes the structure of the app.
"""

from dataclasses import dataclass

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
SEDE_EMPRESA_COMPLETA = "Empresa Completa"  # consolidated view (GERENCIA only)

# Sede options offered at login, per role. GERENCIA additionally sees the
# consolidated "Empresa Completa" scope.
_SEDES_BY_ROLE = {
    ROLE_OPERARIOS: [SEDE_PRINCIPAL, SEDE_SUCURSAL],
    ROLE_ADMINISTRATIVA: [SEDE_PRINCIPAL, SEDE_SUCURSAL],
    ROLE_GERENCIA: [SEDE_PRINCIPAL, SEDE_SUCURSAL, SEDE_EMPRESA_COMPLETA],
}


def get_sedes(role: str) -> list[str]:
    """Return the sede options a role may choose at login."""
    return list(_SEDES_BY_ROLE.get(role, [SEDE_PRINCIPAL, SEDE_SUCURSAL]))


# --------------------------------------------------------------------------- #
# Navigation model
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Page:
    """A leaf menu entry that renders a placeholder page."""

    key: str  # unique across the whole app (used for routing)
    label: str


@dataclass(frozen=True)
class Group:
    """A labelled group of pages (a second navigation level)."""

    label: str
    icon: str
    pages: tuple[Page, ...]


# --- OPERARIOS ------------------------------------------------------------- #
# Same four pages for either sede.
_OPERARIOS_NAV: list = [
    Page("op_inventario", "Inventario"),
    Page("op_alertas", "Alertas"),
    Page("op_historial", "Historial"),
    Page("op_comentarios", "Comentarios"),
]

# --- ÁREA ADMINISTRATIVA --------------------------------------------------- #
_ADMIN_MATERIAL_NUEVO = Group(
    label="Material Nuevo",
    icon="🆕",
    pages=(
        Page("adm_mn_registro_movimiento", "Registro de Movimiento"),
        Page("adm_mn_inventario", "Inventario"),
        Page("adm_mn_gestion_inventario", "Gestión de Inventario"),
        Page("adm_mn_alertas", "Alertas"),
        Page("adm_mn_reporte_ventas", "Reporte de Ventas"),
        Page("adm_mn_historial", "Historial"),
    ),
)

_ADMIN_MATERIAL_SEGUNDO_USO = Group(
    label="Material Segundo Uso",
    icon="♻️",
    pages=(
        Page("adm_msu_registro_movimiento", "Registro de Movimiento"),
        Page("adm_msu_inventario", "Inventario"),
        Page("adm_msu_gestion_inventario", "Gestión de Inventario"),
        Page("adm_msu_alertas", "Alertas"),
        Page("adm_msu_reporte_ventas", "Reporte de Ventas"),
        Page("adm_msu_historial", "Historial"),
    ),
)

_ADMIN_IMPORTAR = Group(
    label="Importar",
    icon="📥",
    pages=(
        Page("adm_importar_productos", "Importar Productos"),
        Page("adm_importar_stock", "Importar Stock"),
    ),
)

_ADMINISTRATIVA_NAV = {
    SEDE_PRINCIPAL: [
        _ADMIN_MATERIAL_NUEVO,
        _ADMIN_MATERIAL_SEGUNDO_USO,
        _ADMIN_IMPORTAR,
        Page("adm_comentarios", "Comentarios"),
    ],
    SEDE_SUCURSAL: [
        _ADMIN_MATERIAL_NUEVO,
        _ADMIN_IMPORTAR,
        Page("adm_comentarios", "Comentarios"),
    ],
}

# --- GERENCIA -------------------------------------------------------------- #
# The import section groups the three separate importers.
_GERENCIA_IMPORTAR = Group(
    label="Importar",
    icon="📥",
    pages=(
        Page("ger_importar_productos", "Importar Productos"),
        Page("ger_importar_stock", "Importar Stock"),
    ),
)

# Same modules regardless of the chosen sede scope (incl. Empresa Completa).
_GERENCIA_NAV: list = [
    Page("ger_productos", "Productos"),
    _GERENCIA_IMPORTAR,
    Page("ger_precios", "Precios"),
    Page("ger_recursos_humanos", "Recursos Humanos"),
    Page("ger_gestion_inventario", "Gestión de Inventario"),
    Page("ger_solicitudes_reposicion", "Solicitudes de Reposición"),
    Page("ger_reportes", "Reportes"),
    Page("ger_balance_financiero", "Balance Financiero"),
    Page("ger_configuracion", "Configuración"),
    Page("ger_comentarios", "Comentarios"),
    Page("ger_auditoria", "Auditoría"),
]


def get_navigation(role: str, sede: str) -> list:
    """Return the navigation items (Page or Group) for a role + sede.

    Args:
        role: One of the ROLE_* constants.
        sede: One of the SEDE_* constants.

    Returns:
        Ordered list whose items are either Page or Group instances.
    """
    if role == ROLE_OPERARIOS:
        return list(_OPERARIOS_NAV)
    if role == ROLE_ADMINISTRATIVA:
        return list(_ADMINISTRATIVA_NAV.get(sede, []))
    if role == ROLE_GERENCIA:
        return list(_GERENCIA_NAV)
    return []
