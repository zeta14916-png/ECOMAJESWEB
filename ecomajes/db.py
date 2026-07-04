"""Database access layer for ECOMAJES ERP.

Thin, dependency-light data access using psycopg2 against the Replit-managed
PostgreSQL database (connection string in the DATABASE_URL env var). A small
connection pool is cached for the Streamlit session.

Only the data operations needed by the current step live here: products
(inventory) and movements (entrada / salida / venta) with atomic stock updates.
"""

import hashlib
import os
import re
import secrets
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation

import psycopg2
import psycopg2.extras
import psycopg2.pool
import streamlit as st

TIPO_NUEVO = "nuevo"
TIPO_SEGUNDO_USO = "segundo_uso"

MOVEMENT_ENTRADA = "entrada"
MOVEMENT_SALIDA = "salida"
MOVEMENT_VENTA = "venta"

# Catálogo de productos — allowed "tipo de venta" (sale type) values.
# Stored on products.tipo_venta (CHECK-constrained in the DB).
VENTA_UNIDAD = "unidad"
VENTA_METRO = "metro"
VENTA_CENTIMETRO = "centimetro"
VENTA_PLANCHA_COMPLETA = "plancha_completa"
VENTA_CORTE_PERSONALIZADO = "corte_personalizado"

# Human-readable labels for material types and movement types.
TIPO_LABELS = {
    TIPO_NUEVO: "Material Nuevo",
    TIPO_SEGUNDO_USO: "Material Segundo Uso",
}
MOVEMENT_LABELS = {
    MOVEMENT_ENTRADA: "Entrada",
    MOVEMENT_SALIDA: "Salida",
    MOVEMENT_VENTA: "Venta",
}
TIPO_VENTA_LABELS = {
    VENTA_UNIDAD: "Unidad",
    VENTA_METRO: "Metro",
    VENTA_CENTIMETRO: "Centímetro",
    VENTA_PLANCHA_COMPLETA: "Plancha completa",
    VENTA_CORTE_PERSONALIZADO: "Corte personalizado",
}

# Movement types that add to stock vs. remove from stock.
_ADDS_STOCK = {MOVEMENT_ENTRADA}
_REMOVES_STOCK = {MOVEMENT_SALIDA, MOVEMENT_VENTA}


@st.cache_resource(show_spinner=False)
def _get_pool() -> psycopg2.pool.SimpleConnectionPool:
    """Create (once) and return a small connection pool."""
    dsn = os.environ["DATABASE_URL"]
    return psycopg2.pool.SimpleConnectionPool(1, 5, dsn=dsn)


@contextmanager
def _get_conn():
    """Borrow a connection from the pool and return it afterwards."""
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)


# --------------------------------------------------------------------------- #
# Products / inventory
# --------------------------------------------------------------------------- #
def list_products(
    sede: str | None = None,
    material_tipo: str | None = None,
    include_all_sedes: bool = False,
) -> list[dict]:
    """Return products, optionally filtered by sede and material type."""
    clauses = []
    params: list = []
    if not include_all_sedes and sede is not None:
        clauses.append("sede = %s")
        params.append(sede)
    if material_tipo is not None:
        clauses.append("material_tipo = %s")
        params.append(material_tipo)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = (
        "SELECT id, sede, material_tipo, nombre, sku, unidad, stock, created_at "
        f"FROM products {where} ORDER BY sede, material_tipo, nombre"
    )
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


def add_product(
    sede: str,
    material_tipo: str,
    nombre: str,
    sku: str | None,
    unidad: str,
    stock_inicial: Decimal,
) -> None:
    """Insert a new product with an initial stock level."""
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO products (sede, material_tipo, nombre, sku, unidad, stock)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (sede, material_tipo, nombre, sku or None, unidad, stock_inicial),
            )
        conn.commit()


# --------------------------------------------------------------------------- #
# Product catalog (catálogo de productos) — extended fields on `products`
# --------------------------------------------------------------------------- #
# Catalog columns edited from the GERENCIA > Productos page. `nombre` is the
# existing NOT NULL / unique identifier; on create it is seeded from the
# descripcion so the catalog only needs to expose the fields below. On update
# `nombre` and `stock` are left untouched (they belong to the inventory view).
CATALOG_FIELDS = (
    "codigo",
    "descripcion",
    "categoria",
    "unidad",
    "tipo_venta",
    "peso",
    "stock_minimo",
    "observaciones",
    "activo",
)


def list_catalog_products(
    sede: str | None = None,
    include_all_sedes: bool = False,
    search: str | None = None,
    material_tipo: str | None = None,
) -> list[dict]:
    """Return catalog products, optionally scoped by sede and a text search.

    The search matches (case-insensitively) against codigo or descripcion.
    An optional material_tipo further scopes the result (additive; callers that
    omit it keep the previous behaviour).
    """
    clauses: list[str] = []
    params: list = []
    if not include_all_sedes and sede is not None:
        clauses.append("sede = %s")
        params.append(sede)
    if material_tipo is not None:
        clauses.append("material_tipo = %s")
        params.append(material_tipo)
    if search:
        clauses.append("(codigo ILIKE %s OR descripcion ILIKE %s)")
        like = f"%{search}%"
        params.extend([like, like])

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = (
        "SELECT id, sede, material_tipo, nombre, codigo, descripcion, categoria, "
        "unidad, tipo_venta, peso, stock_minimo, observaciones, activo, stock, "
        "created_at "
        f"FROM products {where} "
        "ORDER BY codigo NULLS LAST, descripcion NULLS LAST, nombre"
    )
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


def inventory_overview(sede_principal: str, sede_sucursal: str) -> list[dict]:
    """Return one combined row per product (across sedes) for inventory mgmt.

    Products are grouped by (material_tipo, nombre) — the schema's per-sede
    identity — so the same product held in both sedes collapses into a single
    row instead of being duplicated. Per-sede stock is split into principal and
    sucursal columns; representative catalog fields (codigo, descripcion,
    categoria, unidad, stock_minimo) are taken from the group. Presence flags
    (in_principal/in_sucursal) allow the caller to scope by location even when a
    sede holds zero stock. Read-only; does not mutate products or prices.
    """
    sql = (
        "SELECT "
        "  material_tipo, "
        "  nombre, "
        "  MAX(codigo) AS codigo, "
        "  MAX(descripcion) AS descripcion, "
        "  MAX(categoria) AS categoria, "
        "  MAX(unidad) AS unidad, "
        "  COALESCE(SUM(stock) FILTER (WHERE sede = %s), 0) AS stock_principal, "
        "  COALESCE(SUM(stock) FILTER (WHERE sede = %s), 0) AS stock_sucursal, "
        "  COALESCE(MAX(stock_minimo), 0) AS stock_minimo, "
        "  bool_or(sede = %s) AS in_principal, "
        "  bool_or(sede = %s) AS in_sucursal "
        "FROM products "
        "GROUP BY material_tipo, nombre "
        "ORDER BY MAX(codigo) NULLS LAST, MAX(descripcion) NULLS LAST, nombre"
    )
    params = [sede_principal, sede_sucursal, sede_principal, sede_sucursal]
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


def create_catalog_product(
    sede: str,
    descripcion: str,
    codigo: str | None = None,
    categoria: str | None = None,
    unidad: str = "unidad",
    tipo_venta: str = VENTA_UNIDAD,
    peso: Decimal | None = None,
    stock_minimo: Decimal = Decimal("0"),
    observaciones: str | None = None,
    activo: bool = True,
    material_tipo: str = TIPO_NUEVO,
) -> None:
    """Insert a catalog product. `nombre` is seeded from the description."""
    if tipo_venta not in TIPO_VENTA_LABELS:
        raise ValueError(f"Tipo de venta inválido: {tipo_venta}")
    with _get_conn() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO products
                        (sede, material_tipo, nombre, codigo, descripcion,
                         categoria, unidad, tipo_venta, peso, stock_minimo,
                         observaciones, activo)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        sede,
                        material_tipo,
                        descripcion,
                        codigo,
                        descripcion,
                        categoria,
                        unidad,
                        tipo_venta,
                        peso,
                        stock_minimo,
                        observaciones,
                        activo,
                    ),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def update_catalog_product(
    product_id: int,
    descripcion: str,
    codigo: str | None,
    categoria: str | None,
    unidad: str,
    tipo_venta: str,
    peso: Decimal | None,
    stock_minimo: Decimal,
    observaciones: str | None,
    activo: bool,
) -> None:
    """Update the catalog fields of a product (leaves `nombre`/`stock` intact)."""
    if tipo_venta not in TIPO_VENTA_LABELS:
        raise ValueError(f"Tipo de venta inválido: {tipo_venta}")
    with _get_conn() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE products SET
                        codigo = %s, descripcion = %s, categoria = %s,
                        unidad = %s, tipo_venta = %s, peso = %s,
                        stock_minimo = %s, observaciones = %s, activo = %s
                    WHERE id = %s
                    """,
                    (
                        codigo,
                        descripcion,
                        categoria,
                        unidad,
                        tipo_venta,
                        peso,
                        stock_minimo,
                        observaciones,
                        activo,
                        product_id,
                    ),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def set_product_active(product_id: int, activo: bool) -> None:
    """Activate or deactivate a product (Estado)."""
    with _get_conn() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE products SET activo = %s WHERE id = %s",
                    (activo, product_id),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


# --------------------------------------------------------------------------- #
# Excel product import (intelligent importer)
# --------------------------------------------------------------------------- #
# Categories used when auto-classifying a product from its description.
IMPORT_CATEGORIES = [
    "TUBO RECTANGULAR",
    "TUBO REDONDO",
    "TUBO CUADRADO",
    "PLANCHAS",
    "PLATINAS",
    "ANGULOS",
    "DISCOS",
    "EPP",
    "MALLAS",
    "ALAMBRES",
    "PERNERIA",
    "CERRAJERIA",
    "OTROS",
]

# Ordered keyword rules for auto-classification. The first rule with a keyword
# found in the description (matched at a word boundary, so "MANGUERA" does not
# match "ANG") wins. Keywords are uppercased; accents are stripped before match.
_CATEGORY_RULES: list[tuple[tuple[str, ...], str]] = [
    (("RECTANGULAR", "RECT"), "TUBO RECTANGULAR"),
    (("REDONDO", "REDOND", "RED"), "TUBO REDONDO"),
    (("CUADRADO", "CUADR", "CUAD"), "TUBO CUADRADO"),
    (("PLANCHA",), "PLANCHAS"),
    (("PLATINA", "PLAT"), "PLATINAS"),
    (("ANGULO", "ANG"), "ANGULOS"),
    (("DISCO",), "DISCOS"),
    (("GUANTE", "CASCO", "LENTE", "BOTA", "ARNES", "MASCARILLA"), "EPP"),
    (("MALLA",), "MALLAS"),
    (("ALAMBRE",), "ALAMBRES"),
    (("PERNO", "TORNILLO", "TUERCA", "ARANDELA"), "PERNERIA"),
    (("CERRADURA", "CERROJO"), "CERRAJERIA"),
]


def _strip_accents(text: str) -> str:
    """Fold the Spanish accents that appear in product descriptions."""
    for a, b in (
        ("Á", "A"),
        ("É", "E"),
        ("Í", "I"),
        ("Ó", "O"),
        ("Ú", "U"),
        ("Ñ", "N"),
    ):
        text = text.replace(a, b)
    return text


def classify_categoria(descripcion: str | None) -> str:
    """Best-effort category from a product description (keyword rules).

    Keywords match at a word boundary (prefix), so short abbreviations like
    "ANG" classify "ANGULO 1x1" but never "MANGUERA".
    """
    text = _strip_accents((descripcion or "").upper())
    for keywords, categoria in _CATEGORY_RULES:
        pattern = r"\b(" + "|".join(re.escape(k) for k in keywords) + r")"
        if re.search(pattern, text):
            return categoria
    return "OTROS"


def resolve_categoria(provided: str | None, descripcion: str | None) -> str:
    """Return a valid category: keep the provided one if valid, else classify.

    A provided category is "valid" only when it matches one of
    ``IMPORT_CATEGORIES`` (case-insensitive). Empty or unrecognized categories
    fall back to :func:`classify_categoria`.
    """
    candidate = (provided or "").strip().upper()
    if candidate in IMPORT_CATEGORIES:
        return candidate
    return classify_categoria(descripcion)


def _fullest(a: str | None, b: str | None) -> str:
    """Return the clearest/fullest of two descriptions (the longer non-empty)."""
    a = (a or "").strip()
    b = (b or "").strip()
    if not a:
        return b
    if not b:
        return a
    return a if len(a) >= len(b) else b


def _import_decimal(value) -> Decimal | None:
    """Parse a spreadsheet money/number cell to Decimal, or None when empty.

    Tolerates currency prefixes ("S/") and thousands separators.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = (
        text.replace("S/", "")
        .replace("s/", "")
        .replace(" ", "")
        .replace(",", "")
    )
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _upsert_import_price(
    cur,
    product_id: int,
    codigo: str | None,
    descripcion: str | None,
    categoria: str | None,
    unidad: str | None,
    precio: Decimal | None,
    costo: Decimal | None,
) -> None:
    """Upsert the pricing/cost row for an imported product.

    Only fills precio/precio_sugerido/costo when the import supplies a value
    (COALESCE keeps any existing manually-edited value otherwise), and seeds the
    display columns (codigo/descripcion/categoria/unidad) without overwriting
    values already curated in the Precios sheet. Does not touch p1/p2/p3,
    precio_minimo, peso or observaciones.
    """
    cur.execute(
        """
        INSERT INTO prices
            (product_id, codigo, descripcion, categoria, unidad,
             precio, precio_sugerido, costo)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (product_id) DO UPDATE SET
            precio = COALESCE(EXCLUDED.precio, prices.precio),
            precio_sugerido = COALESCE(
                EXCLUDED.precio_sugerido, prices.precio_sugerido
            ),
            costo = COALESCE(EXCLUDED.costo, prices.costo),
            codigo = COALESCE(prices.codigo, EXCLUDED.codigo),
            descripcion = COALESCE(prices.descripcion, EXCLUDED.descripcion),
            categoria = COALESCE(prices.categoria, EXCLUDED.categoria),
            unidad = COALESCE(prices.unidad, EXCLUDED.unidad),
            updated_at = now()
        """,
        (
            product_id,
            codigo,
            descripcion,
            categoria,
            unidad,
            precio,
            precio,  # seed precio_sugerido from the sale price
            costo,
        ),
    )


def import_products(
    rows: list[dict],
    sede: str,
    material_tipo: str = TIPO_NUEVO,
) -> dict:
    """Import/upsert catalog products from a parsed spreadsheet.

    Each row may contain: codigo, descripcion, unidad, categoria, stock,
    precio_venta, costo, familia. Rows should already be de-duplicated by codigo
    (the caller collapses repeats and reports how many were skipped). Matching is
    by codigo (globally unique): an existing codigo updates that product keeping
    the fullest description; otherwise a new product is inserted into
    (sede, material_tipo). Rows without a codigo are matched by nombre
    (= descripcion) within the sede/material_tipo. Missing unidad defaults to
    "UNIDAD", missing categoria is auto-classified, missing stock defaults to 0.

    Additionally: precio_venta -> prices.precio (+ precio_sugerido), costo ->
    prices.costo (both via `_upsert_import_price`, non-destructive when absent),
    and familia -> products.familia (kept when the import omits it). The Precios
    sheet UI is unchanged (it never reads/writes costo/familia).

    Returns counts: {"inserted", "updated", "errors", "error_details"}.
    """
    inserted = 0
    updated = 0
    errors = 0
    error_details: list[str] = []

    with _get_conn() as conn:
        try:
            with conn.cursor() as cur:
                for row in rows:
                    codigo = (str(row.get("codigo") or "")).strip() or None
                    descripcion = (str(row.get("descripcion") or "")).strip()
                    if not descripcion and not codigo:
                        continue
                    unidad = (str(row.get("unidad") or "")).strip() or "UNIDAD"
                    categoria = resolve_categoria(
                        row.get("categoria"), descripcion
                    )
                    try:
                        stock = Decimal(str(row.get("stock") or 0))
                    except (InvalidOperation, ValueError, TypeError):
                        stock = Decimal("0")
                    precio = _import_decimal(row.get("precio_venta"))
                    costo = _import_decimal(row.get("costo"))
                    familia = (str(row.get("familia") or "")).strip() or None

                    try:
                        cur.execute("SAVEPOINT sp_row")
                        existing = None
                        if codigo is not None:
                            cur.execute(
                                "SELECT id, descripcion FROM products "
                                "WHERE codigo = %s",
                                (codigo,),
                            )
                            existing = cur.fetchone()
                        elif descripcion:
                            cur.execute(
                                "SELECT id, descripcion FROM products "
                                "WHERE sede = %s AND material_tipo = %s "
                                "AND nombre = %s",
                                (sede, material_tipo, descripcion),
                            )
                            existing = cur.fetchone()

                        if existing is not None:
                            pid, old_desc = existing
                            cur.execute(
                                """
                                UPDATE products SET
                                    descripcion = %s,
                                    categoria = %s,
                                    unidad = %s,
                                    familia = COALESCE(%s, familia)
                                WHERE id = %s
                                """,
                                (
                                    _fullest(old_desc, descripcion),
                                    categoria,
                                    unidad,
                                    familia,
                                    pid,
                                ),
                            )
                            updated += 1
                        else:
                            nombre = descripcion or codigo or "PRODUCTO"
                            cur.execute(
                                "SELECT 1 FROM products "
                                "WHERE sede = %s AND material_tipo = %s "
                                "AND nombre = %s",
                                (sede, material_tipo, nombre),
                            )
                            if cur.fetchone() is not None:
                                if codigo:
                                    nombre = f"{nombre} ({codigo})"
                                else:
                                    raise ValueError(
                                        "Nombre duplicado sin código"
                                    )
                            cur.execute(
                                """
                                INSERT INTO products
                                    (sede, material_tipo, nombre, codigo,
                                     descripcion, categoria, unidad, stock,
                                     familia, activo)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                                RETURNING id
                                """,
                                (
                                    sede,
                                    material_tipo,
                                    nombre,
                                    codigo,
                                    descripcion,
                                    categoria,
                                    unidad,
                                    stock,
                                    familia,
                                ),
                            )
                            pid = cur.fetchone()[0]
                            inserted += 1

                        # Store pricing/cost data only when supplied.
                        if precio is not None or costo is not None:
                            _upsert_import_price(
                                cur,
                                pid,
                                codigo,
                                descripcion,
                                categoria,
                                unidad,
                                precio,
                                costo,
                            )
                        cur.execute("RELEASE SAVEPOINT sp_row")
                    except Exception as exc:  # noqa: BLE001
                        cur.execute("ROLLBACK TO SAVEPOINT sp_row")
                        errors += 1
                        error_details.append(f"{codigo or descripcion}: {exc}")
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return {
        "inserted": inserted,
        "updated": updated,
        "errors": errors,
        "error_details": error_details,
    }


# --------------------------------------------------------------------------- #
# Prices (price list linked to products)
# --------------------------------------------------------------------------- #
# Editable price fields stored in the `prices` table (one row per product).
PRICE_FIELDS = (
    "codigo",
    "descripcion",
    "categoria",
    "unidad",
    "peso",
    "precio",
    "p1",
    "p2",
    "p3",
    "precio_minimo",
    "precio_sugerido",
    "observaciones",
)


def list_prices(
    sede: str | None = None,
    material_tipo: str | None = None,
    include_all_sedes: bool = False,
) -> list[dict]:
    """Return products joined with their price row (LEFT JOIN).

    Products without a price row still appear (price fields are NULL) so the
    price sheet can seed defaults from product data.
    """
    clauses = []
    params: list = []
    if not include_all_sedes and sede is not None:
        clauses.append("p.sede = %s")
        params.append(sede)
    if material_tipo is not None:
        clauses.append("p.material_tipo = %s")
        params.append(material_tipo)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = (
        "SELECT p.id AS product_id, p.sede, p.material_tipo, p.nombre, "
        "p.sku, p.unidad AS producto_unidad, "
        "pr.codigo, pr.descripcion, pr.categoria, pr.unidad, pr.peso, "
        "pr.precio, pr.p1, pr.p2, pr.p3, pr.precio_minimo, "
        "pr.precio_sugerido, pr.observaciones "
        "FROM products p LEFT JOIN prices pr ON pr.product_id = p.id "
        f"{where} ORDER BY p.sede, p.material_tipo, p.nombre"
    )
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


def save_prices(rows: list[dict]) -> int:
    """Upsert a batch of price rows (one per product_id).

    Each row must contain "product_id" plus any subset of PRICE_FIELDS.
    Returns the number of rows written.
    """
    if not rows:
        return 0

    columns = ["product_id", *PRICE_FIELDS]
    placeholders = ", ".join(["%s"] * len(columns))
    updates = ", ".join(f"{f} = EXCLUDED.{f}" for f in PRICE_FIELDS)
    sql = (
        f"INSERT INTO prices ({', '.join(columns)}) VALUES ({placeholders}) "
        f"ON CONFLICT (product_id) DO UPDATE SET {updates}, updated_at = now()"
    )
    with _get_conn() as conn:
        try:
            with conn.cursor() as cur:
                for row in rows:
                    values = [row["product_id"]] + [
                        row.get(f) for f in PRICE_FIELDS
                    ]
                    cur.execute(sql, values)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return len(rows)


def get_price(product_id: int) -> dict | None:
    """Return the price row for a product, or None if none is configured."""
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM prices WHERE product_id = %s", (product_id,)
            )
            row = cur.fetchone()
            return dict(row) if row else None


# --------------------------------------------------------------------------- #
# Movements (stock updates)
# --------------------------------------------------------------------------- #
class StockError(Exception):
    """Raised when a movement cannot be applied (e.g. insufficient stock)."""


def register_movement(
    product_id: int,
    tipo: str,
    cantidad: Decimal,
    nota: str | None,
    usuario_rol: str | None,
    sede: str | None,
    tipo_venta: str | None = None,
    precio_final: Decimal | None = None,
    autorizado_por: str | None = None,
) -> Decimal:
    """Register a movement and update the product stock atomically.

    Returns the resulting stock. Raises StockError for an unknown product or
    when a salida/venta would drive stock negative.

    Sales (``venta``) optionally carry a sale type (``tipo_venta``). For special
    sales (metro / centímetro / corte personalizado) the caller passes an
    explicit ``precio_final`` (the total amount charged) and, optionally, who
    authorised it (``autorizado_por``). ``precio_final`` is stored as
    ``precio_total`` so every report that sums ``precio_total`` uses the final
    price. When ``precio_final`` is not given (a plain unit sale), the configured
    unit price is snapshotted from ``prices`` exactly as before. This function
    NEVER derives or changes anything other than the primary stock movement.
    """
    if tipo not in _ADDS_STOCK | _REMOVES_STOCK:
        raise StockError(f"Tipo de movimiento inválido: {tipo}")
    if tipo_venta is not None and tipo_venta not in TIPO_VENTA_LABELS:
        raise StockError(f"Tipo de venta inválido: {tipo_venta}")

    with _get_conn() as conn:
        try:
            with conn.cursor() as cur:
                # Lock the product row for the duration of the transaction.
                cur.execute(
                    "SELECT stock FROM products WHERE id = %s FOR UPDATE",
                    (product_id,),
                )
                row = cur.fetchone()
                if row is None:
                    raise StockError("El producto no existe.")

                current = row[0]
                delta = cantidad if tipo in _ADDS_STOCK else -cantidad
                new_stock = current + delta
                if new_stock < 0:
                    raise StockError(
                        f"Stock insuficiente: disponible {current}, "
                        f"solicitado {cantidad}."
                    )

                cur.execute(
                    "UPDATE products SET stock = %s WHERE id = %s",
                    (new_stock, product_id),
                )

                # Sale pricing: an explicit precio_final (special sales) wins and
                # is stored as precio_total so reports use it; otherwise snapshot
                # the configured unit price (plain unit sale, unchanged).
                precio_unitario = None
                precio_total = None
                stored_tipo_venta = None
                stored_autorizado = None
                if tipo == MOVEMENT_VENTA:
                    stored_tipo_venta = tipo_venta or VENTA_UNIDAD
                    stored_autorizado = autorizado_por
                    if precio_final is not None:
                        precio_total = precio_final
                        precio_unitario = (
                            precio_final / cantidad
                            if cantidad and cantidad != 0
                            else precio_final
                        )
                    else:
                        cur.execute(
                            "SELECT precio FROM prices WHERE product_id = %s",
                            (product_id,),
                        )
                        prow = cur.fetchone()
                        if prow is not None and prow[0] is not None:
                            precio_unitario = prow[0]
                            precio_total = precio_unitario * cantidad

                cur.execute(
                    """
                    INSERT INTO movements
                        (product_id, tipo, cantidad, nota, usuario_rol, sede,
                         precio_unitario, precio_total, tipo_venta,
                         autorizado_por)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        product_id,
                        tipo,
                        cantidad,
                        nota or None,
                        usuario_rol,
                        sede,
                        precio_unitario,
                        precio_total,
                        stored_tipo_venta,
                        stored_autorizado,
                    ),
                )
            conn.commit()
            return new_stock
        except Exception:
            conn.rollback()
            raise


# --------------------------------------------------------------------------- #
# Sales reports: sales (derived from venta movements), expenses, observations
# --------------------------------------------------------------------------- #
def _date_scope_clauses(
    sede: str | None,
    include_all_sedes: bool,
    date_from,
    date_to,
    sede_col: str,
    date_col: str,
) -> tuple[list[str], list]:
    """Build shared WHERE clauses for sede + date-range filtering."""
    clauses: list[str] = []
    params: list = []
    if not include_all_sedes and sede is not None:
        clauses.append(f"{sede_col} = %s")
        params.append(sede)
    if date_from is not None:
        clauses.append(f"{date_col} >= %s")
        params.append(date_from)
    if date_to is not None:
        clauses.append(f"{date_col} <= %s")
        params.append(date_to)
    return clauses, params


def list_sales(
    sede: str | None = None,
    include_all_sedes: bool = False,
    date_from=None,
    date_to=None,
) -> list[dict]:
    """Return individual sales (venta movements) with full detail.

    Each row carries date, user, product, quantity, unit price, total price and
    location, satisfying the "every sale must include ..." requirement.
    """
    clauses = ["m.tipo = %s"]
    params: list = [MOVEMENT_VENTA]
    extra_clauses, extra_params = _date_scope_clauses(
        sede, include_all_sedes, date_from, date_to, "m.sede", "m.created_at::date"
    )
    clauses.extend(extra_clauses)
    params.extend(extra_params)

    where = f"WHERE {' AND '.join(clauses)}"
    sql = (
        "SELECT m.id, m.created_at, m.usuario_rol, m.cantidad, "
        "m.precio_unitario, m.precio_total, m.sede, "
        "p.nombre AS producto, p.unidad "
        "FROM movements m JOIN products p ON p.id = m.product_id "
        f"{where} ORDER BY m.created_at DESC"
    )
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


def add_expense(
    fecha,
    descripcion: str,
    monto: Decimal,
    sede: str,
    usuario_rol: str | None,
) -> None:
    """Record a daily expense for a location."""
    with _get_conn() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO expenses (fecha, descripcion, monto, sede, usuario_rol)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (fecha, descripcion, monto, sede, usuario_rol),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def list_expenses(
    sede: str | None = None,
    include_all_sedes: bool = False,
    date_from=None,
    date_to=None,
) -> list[dict]:
    """Return expenses filtered by location and date range."""
    clauses, params = _date_scope_clauses(
        sede, include_all_sedes, date_from, date_to, "sede", "fecha"
    )
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = (
        "SELECT id, fecha, descripcion, monto, sede, usuario_rol, created_at "
        f"FROM expenses {where} ORDER BY fecha DESC, id DESC"
    )
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


def add_observation(
    fecha,
    sede: str,
    observacion: str,
    usuario_rol: str | None,
) -> None:
    """Record a daily observation for a location."""
    with _get_conn() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO daily_observations
                        (fecha, sede, observacion, usuario_rol)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (fecha, sede, observacion, usuario_rol),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def list_observations(
    sede: str | None = None,
    include_all_sedes: bool = False,
    date_from=None,
    date_to=None,
) -> list[dict]:
    """Return observations filtered by location and date range."""
    clauses, params = _date_scope_clauses(
        sede, include_all_sedes, date_from, date_to, "sede", "fecha"
    )
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = (
        "SELECT id, fecha, sede, observacion, usuario_rol, created_at "
        f"FROM daily_observations {where} ORDER BY fecha DESC, id DESC"
    )
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


def financial_summary(
    sede: str | None = None,
    include_all_sedes: bool = False,
    date_from=None,
    date_to=None,
) -> dict:
    """Aggregate sales + expenses into the metrics used by reports.

    Returns a dict with total_sales (transaction count), total_products
    (units sold), total_revenue, total_expenses and net_income. This is the
    shared data structure that Balance Financiero will reuse later.
    """
    # Sales aggregates from venta movements.
    sales_clauses = ["tipo = %s"]
    sales_params: list = [MOVEMENT_VENTA]
    c, p = _date_scope_clauses(
        sede, include_all_sedes, date_from, date_to, "sede", "created_at::date"
    )
    sales_clauses.extend(c)
    sales_params.extend(p)
    sales_sql = (
        "SELECT COUNT(*) AS total_sales, "
        "COALESCE(SUM(cantidad), 0) AS total_products, "
        "COALESCE(SUM(precio_total), 0) AS total_revenue "
        f"FROM movements WHERE {' AND '.join(sales_clauses)}"
    )

    # Expense aggregate.
    exp_clauses, exp_params = _date_scope_clauses(
        sede, include_all_sedes, date_from, date_to, "sede", "fecha"
    )
    exp_where = f"WHERE {' AND '.join(exp_clauses)}" if exp_clauses else ""
    exp_sql = (
        f"SELECT COALESCE(SUM(monto), 0) AS total_expenses FROM expenses {exp_where}"
    )

    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sales_sql, sales_params)
            sales = cur.fetchone()
            cur.execute(exp_sql, exp_params)
            expenses = cur.fetchone()

    total_revenue = Decimal(sales["total_revenue"])
    total_expenses = Decimal(expenses["total_expenses"])
    return {
        "total_sales": int(sales["total_sales"]),
        "total_products": Decimal(sales["total_products"]),
        "total_revenue": total_revenue,
        "total_expenses": total_expenses,
        "net_income": total_revenue - total_expenses,
    }


def list_movements(
    sede: str | None = None,
    material_tipo: str | None = None,
    include_all_sedes: bool = False,
    limit: int = 50,
) -> list[dict]:
    """Return recent movements joined with product info."""
    clauses = []
    params: list = []
    if not include_all_sedes and sede is not None:
        clauses.append("p.sede = %s")
        params.append(sede)
    if material_tipo is not None:
        clauses.append("p.material_tipo = %s")
        params.append(material_tipo)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = (
        "SELECT m.id, m.tipo, m.cantidad, m.nota, m.usuario_rol, m.created_at, "
        "m.precio_unitario, m.precio_total, m.tipo_venta, m.autorizado_por, "
        "p.nombre AS producto, p.unidad, p.sede, p.material_tipo "
        "FROM movements m JOIN products p ON p.id = m.product_id "
        f"{where} ORDER BY m.created_at DESC LIMIT %s"
    )
    params.append(limit)
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


def list_movements_range(
    sede: str | None = None,
    include_all_sedes: bool = False,
    date_from=None,
    date_to=None,
    material_tipo: str | None = None,
    limit: int = 500,
) -> list[dict]:
    """Recent movements within an optional date range (read-only, additive).

    Same shape as ``list_movements`` but supports date_from/date_to so reports
    can scope inventory movements to the selected period. Does not change any
    existing behaviour.
    """
    clauses: list[str] = []
    params: list = []
    if not include_all_sedes and sede is not None:
        clauses.append("p.sede = %s")
        params.append(sede)
    if material_tipo is not None:
        clauses.append("p.material_tipo = %s")
        params.append(material_tipo)
    if date_from is not None:
        clauses.append("m.created_at::date >= %s")
        params.append(date_from)
    if date_to is not None:
        clauses.append("m.created_at::date <= %s")
        params.append(date_to)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = (
        "SELECT m.id, m.tipo, m.cantidad, m.nota, m.usuario_rol, m.created_at, "
        "m.precio_unitario, m.precio_total, "
        "p.nombre AS producto, p.unidad, p.sede, p.material_tipo "
        "FROM movements m JOIN products p ON p.id = m.product_id "
        f"{where} ORDER BY m.created_at DESC LIMIT %s"
    )
    params.append(limit)
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


# --------------------------------------------------------------------------- #
# Dashboard / Balance Financiero aggregations (read-only, additive)
# --------------------------------------------------------------------------- #
# Stock at or below this level (but above 0) counts as "stock bajo".
LOW_STOCK_THRESHOLD = Decimal("5")

_SIN_CATEGORIA = "(Sin categoría)"


def list_categories(
    sede: str | None = None,
    include_all_sedes: bool = False,
) -> list[str]:
    """Return the distinct product categories in scope (from prices.categoria)."""
    clauses: list[str] = []
    params: list = []
    if not include_all_sedes and sede is not None:
        clauses.append("p.sede = %s")
        params.append(sede)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = (
        f"SELECT DISTINCT COALESCE(pr.categoria, '{_SIN_CATEGORIA}') AS categoria "
        "FROM products p LEFT JOIN prices pr ON pr.product_id = p.id "
        f"{where} ORDER BY categoria"
    )
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [row["categoria"] for row in cur.fetchall()]


def list_inventory(
    sede: str | None = None,
    include_all_sedes: bool = False,
    categoria: str | None = None,
) -> list[dict]:
    """Return products with their category and stock (for dashboard/alerts)."""
    clauses: list[str] = []
    params: list = []
    if not include_all_sedes and sede is not None:
        clauses.append("p.sede = %s")
        params.append(sede)
    if categoria:
        clauses.append(f"COALESCE(pr.categoria, '{_SIN_CATEGORIA}') = %s")
        params.append(categoria)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = (
        "SELECT p.id, p.sede, p.material_tipo, p.nombre, p.unidad, p.stock, "
        f"COALESCE(pr.categoria, '{_SIN_CATEGORIA}') AS categoria "
        "FROM products p LEFT JOIN prices pr ON pr.product_id = p.id "
        f"{where} ORDER BY p.sede, categoria, p.nombre"
    )
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


def _sales_where(
    sede: str | None,
    include_all_sedes: bool,
    date_from,
    date_to,
    categoria: str | None,
) -> tuple[list[str], list]:
    """WHERE clauses for venta aggregations (joins prices for category)."""
    clauses = ["m.tipo = %s"]
    params: list = [MOVEMENT_VENTA]
    if not include_all_sedes and sede is not None:
        clauses.append("m.sede = %s")
        params.append(sede)
    if date_from is not None:
        clauses.append("m.created_at::date >= %s")
        params.append(date_from)
    if date_to is not None:
        clauses.append("m.created_at::date <= %s")
        params.append(date_to)
    if categoria:
        clauses.append(f"COALESCE(pr.categoria, '{_SIN_CATEGORIA}') = %s")
        params.append(categoria)
    return clauses, params


def _run_sales_agg(select: str, tail: str, clauses, params) -> list[dict]:
    sql = (
        f"SELECT {select} FROM movements m "
        "JOIN products p ON p.id = m.product_id "
        "LEFT JOIN prices pr ON pr.product_id = p.id "
        f"WHERE {' AND '.join(clauses)} {tail}"
    )
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


def sales_by_day(
    sede=None, include_all_sedes=False, date_from=None, date_to=None, categoria=None
) -> list[dict]:
    """Total revenue and units per calendar day."""
    clauses, params = _sales_where(
        sede, include_all_sedes, date_from, date_to, categoria
    )
    return _run_sales_agg(
        "m.created_at::date AS dia, "
        "COALESCE(SUM(m.precio_total), 0) AS total, "
        "COALESCE(SUM(m.cantidad), 0) AS unidades",
        "GROUP BY dia ORDER BY dia",
        clauses,
        params,
    )


def sales_by_month(
    sede=None, include_all_sedes=False, date_from=None, date_to=None, categoria=None
) -> list[dict]:
    """Total revenue per month (YYYY-MM)."""
    clauses, params = _sales_where(
        sede, include_all_sedes, date_from, date_to, categoria
    )
    return _run_sales_agg(
        "to_char(date_trunc('month', m.created_at), 'YYYY-MM') AS mes, "
        "COALESCE(SUM(m.precio_total), 0) AS total",
        "GROUP BY mes ORDER BY mes",
        clauses,
        params,
    )


def sales_by_product(
    sede=None,
    include_all_sedes=False,
    date_from=None,
    date_to=None,
    categoria=None,
    order: str = "desc",
    limit: int = 10,
) -> list[dict]:
    """Units + revenue per product, ordered by units sold (most/least)."""
    clauses, params = _sales_where(
        sede, include_all_sedes, date_from, date_to, categoria
    )
    direction = "ASC" if str(order).lower() == "asc" else "DESC"
    params = list(params) + [limit]
    return _run_sales_agg(
        "p.id AS product_id, p.nombre AS producto, "
        "p.sede AS sede, p.material_tipo AS material_tipo, "
        "COALESCE(SUM(m.cantidad), 0) AS unidades, "
        "COALESCE(SUM(m.precio_total), 0) AS total",
        "GROUP BY p.id, p.nombre, p.sede, p.material_tipo "
        f"ORDER BY unidades {direction}, p.nombre LIMIT %s",
        clauses,
        params,
    )


def sales_by_location(date_from=None, date_to=None, categoria=None) -> list[dict]:
    """Total revenue per sede (always compares all locations)."""
    clauses, params = _sales_where(None, True, date_from, date_to, categoria)
    return _run_sales_agg(
        "m.sede AS sede, COALESCE(SUM(m.precio_total), 0) AS total",
        "GROUP BY m.sede ORDER BY m.sede",
        clauses,
        params,
    )


def expenses_by_month(
    sede=None, include_all_sedes=False, date_from=None, date_to=None
) -> list[dict]:
    """Total expenses per month (YYYY-MM)."""
    clauses, params = _date_scope_clauses(
        sede, include_all_sedes, date_from, date_to, "sede", "fecha"
    )
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = (
        "SELECT to_char(date_trunc('month', fecha), 'YYYY-MM') AS mes, "
        "COALESCE(SUM(monto), 0) AS total "
        f"FROM expenses {where} GROUP BY mes ORDER BY mes"
    )
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


# --------------------------------------------------------------------------- #
# Recursos Humanos: employees + payroll
# --------------------------------------------------------------------------- #
# Employee status values (Estado).
EMPLOYEE_ACTIVO = "activo"
EMPLOYEE_INACTIVO = "inactivo"
EMPLOYEE_STATUS_LABELS = {
    EMPLOYEE_ACTIVO: "Activo",
    EMPLOYEE_INACTIVO: "Inactivo",
}


class EmployeeError(Exception):
    """Raised when an employee operation fails (e.g. duplicate username)."""


def _hash_password(password: str) -> tuple[str, str]:
    """Return (hash, salt) for a plaintext password (salted SHA-256)."""
    salt = secrets.token_hex(16)
    digest = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return digest, salt


def verify_employee_password(employee_id: int, password: str) -> bool:
    """Check a plaintext password against the stored salted hash.

    Not yet wired into the login flow; provided so employee credentials can be
    verified later without changing this data layer.
    """
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT password_hash, password_salt FROM employees WHERE id = %s",
                (employee_id,),
            )
            row = cur.fetchone()
    if row is None:
        return False
    digest = hashlib.sha256(
        (row["password_salt"] + password).encode("utf-8")
    ).hexdigest()
    return secrets.compare_digest(digest, row["password_hash"])


def create_employee(
    nombre: str,
    username: str,
    password: str,
    rol: str,
    estado: str = EMPLOYEE_ACTIVO,
    telefono: str | None = None,
    direccion: str | None = None,
    fecha_ingreso=None,
    salario: Decimal = Decimal("0"),
) -> None:
    """Insert a new employee. Password is stored salted+hashed."""
    if estado not in EMPLOYEE_STATUS_LABELS:
        raise ValueError(f"Estado inválido: {estado}")
    password_hash, password_salt = _hash_password(password)
    with _get_conn() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO employees
                        (nombre, username, password_hash, password_salt, rol,
                         estado, telefono, direccion, fecha_ingreso, salario)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        nombre,
                        username,
                        password_hash,
                        password_salt,
                        rol,
                        estado,
                        telefono,
                        direccion,
                        fecha_ingreso,
                        salario,
                    ),
                )
            conn.commit()
        except psycopg2.errors.UniqueViolation as exc:
            conn.rollback()
            raise EmployeeError(
                "Ya existe un empleado con ese nombre de usuario."
            ) from exc
        except Exception:
            conn.rollback()
            raise


def list_employees(
    include_inactive: bool = True,
    search: str | None = None,
) -> list[dict]:
    """Return employees, optionally filtered by status and a text search.

    The search matches (case-insensitively) against nombre or username.
    """
    clauses: list[str] = []
    params: list = []
    if not include_inactive:
        clauses.append("estado = %s")
        params.append(EMPLOYEE_ACTIVO)
    if search:
        clauses.append("(nombre ILIKE %s OR username ILIKE %s)")
        like = f"%{search}%"
        params.extend([like, like])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = (
        "SELECT id, nombre, username, rol, estado, telefono, direccion, "
        "fecha_ingreso, salario, created_at "
        f"FROM employees {where} ORDER BY nombre"
    )
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


def get_employee(employee_id: int) -> dict | None:
    """Return a single employee (without password fields), or None."""
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, nombre, username, rol, estado, telefono, direccion, "
                "fecha_ingreso, salario, created_at "
                "FROM employees WHERE id = %s",
                (employee_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def update_employee(
    employee_id: int,
    nombre: str,
    username: str,
    rol: str,
    estado: str,
    telefono: str | None,
    direccion: str | None,
    fecha_ingreso,
    salario: Decimal,
    password: str | None = None,
) -> None:
    """Update an employee. If `password` is provided, it is re-hashed."""
    if estado not in EMPLOYEE_STATUS_LABELS:
        raise ValueError(f"Estado inválido: {estado}")
    fields = [
        "nombre = %s",
        "username = %s",
        "rol = %s",
        "estado = %s",
        "telefono = %s",
        "direccion = %s",
        "fecha_ingreso = %s",
        "salario = %s",
    ]
    params: list = [
        nombre,
        username,
        rol,
        estado,
        telefono,
        direccion,
        fecha_ingreso,
        salario,
    ]
    if password:
        password_hash, password_salt = _hash_password(password)
        fields.extend(["password_hash = %s", "password_salt = %s"])
        params.extend([password_hash, password_salt])
    params.append(employee_id)
    sql = f"UPDATE employees SET {', '.join(fields)} WHERE id = %s"
    with _get_conn() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
            conn.commit()
        except psycopg2.errors.UniqueViolation as exc:
            conn.rollback()
            raise EmployeeError(
                "Ya existe un empleado con ese nombre de usuario."
            ) from exc
        except Exception:
            conn.rollback()
            raise


def set_employee_status(employee_id: int, estado: str) -> None:
    """Activate or deactivate an employee (Estado)."""
    if estado not in EMPLOYEE_STATUS_LABELS:
        raise ValueError(f"Estado inválido: {estado}")
    with _get_conn() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE employees SET estado = %s WHERE id = %s",
                    (estado, employee_id),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def register_payroll_payment(
    employee_id: int,
    fecha,
    salario: Decimal,
    bono: Decimal = Decimal("0"),
    adelanto: Decimal = Decimal("0"),
    descuento: Decimal = Decimal("0"),
    observacion: str | None = None,
    usuario_rol: str | None = None,
) -> dict:
    """Register a payroll payment; computes pago_final and stores the record.

    pago_final = salario + bono - adelanto - descuento. Returns the inserted
    row. Each payment is stored so Balance Financiero can consume it later via
    ``payroll_total`` (integration prepared, not yet wired into balance).
    """
    salario = Decimal(str(salario))
    bono = Decimal(str(bono))
    adelanto = Decimal(str(adelanto))
    descuento = Decimal(str(descuento))
    pago_final = salario + bono - adelanto - descuento
    with _get_conn() as conn:
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    INSERT INTO payroll_payments
                        (employee_id, fecha, salario, bono, adelanto, descuento,
                         pago_final, observacion, usuario_rol)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, employee_id, fecha, salario, bono, adelanto,
                              descuento, pago_final, observacion, usuario_rol,
                              created_at
                    """,
                    (
                        employee_id,
                        fecha,
                        salario,
                        bono,
                        adelanto,
                        descuento,
                        pago_final,
                        observacion,
                        usuario_rol,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
            return dict(row)
        except Exception:
            conn.rollback()
            raise


def list_payroll_payments(
    employee_id: int | None = None,
    date_from=None,
    date_to=None,
) -> list[dict]:
    """Return payroll payment history joined with the employee name."""
    clauses: list[str] = []
    params: list = []
    if employee_id is not None:
        clauses.append("pp.employee_id = %s")
        params.append(employee_id)
    if date_from is not None:
        clauses.append("pp.fecha >= %s")
        params.append(date_from)
    if date_to is not None:
        clauses.append("pp.fecha <= %s")
        params.append(date_to)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = (
        "SELECT pp.id, pp.employee_id, e.nombre AS empleado, pp.fecha, "
        "pp.salario, pp.bono, pp.adelanto, pp.descuento, pp.pago_final, "
        "pp.observacion, pp.usuario_rol, pp.created_at "
        "FROM payroll_payments pp JOIN employees e ON e.id = pp.employee_id "
        f"{where} ORDER BY pp.fecha DESC, pp.id DESC"
    )
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


def payroll_total(date_from=None, date_to=None) -> Decimal:
    """Total payroll paid (sum of pago_final) within an optional date range.

    Integration point for Balance Financiero: payroll payments are a labor
    expense the balance can add later. Returns a Decimal (0 when none).
    """
    clauses: list[str] = []
    params: list = []
    if date_from is not None:
        clauses.append("fecha >= %s")
        params.append(date_from)
    if date_to is not None:
        clauses.append("fecha <= %s")
        params.append(date_to)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT COALESCE(SUM(pago_final), 0) AS total FROM payroll_payments {where}"
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
    return Decimal(row["total"])


# --------------------------------------------------------------------------- #
# Comentarios (comments) + Auditoría (audit log)
# --------------------------------------------------------------------------- #

# Comment status keys (stored on comments.estado, CHECK-constrained) + labels.
COMMENT_PENDIENTE = "pendiente"
COMMENT_EN_REVISION = "en_revision"
COMMENT_ATENDIDO = "atendido"
COMMENT_STATUS_LABELS = {
    COMMENT_PENDIENTE: "Pendiente",
    COMMENT_EN_REVISION: "En revisión",
    COMMENT_ATENDIDO: "Atendido",
}

# Audit action keys (stored on audit_log.accion) + labels for display.
AUDIT_LOGIN = "login"
AUDIT_PRODUCT_CREATED = "producto_creado"
AUDIT_PRODUCT_UPDATED = "producto_editado"
AUDIT_PRODUCT_DEACTIVATED = "producto_desactivado"
AUDIT_PRODUCT_ACTIVATED = "producto_activado"
AUDIT_PRICE_CHANGED = "precio_actualizado"
AUDIT_MOVEMENT = "movimiento_inventario"
AUDIT_SALES_REPORT = "reporte_generado"
AUDIT_EXPENSE = "gasto_creado"
AUDIT_PAYROLL = "pago_nomina"
AUDIT_IMPORT = "productos_importados"
AUDIT_ACTION_LABELS = {
    AUDIT_LOGIN: "Inicio de sesión",
    AUDIT_PRODUCT_CREATED: "Producto creado",
    AUDIT_PRODUCT_UPDATED: "Producto editado",
    AUDIT_PRODUCT_DEACTIVATED: "Producto desactivado",
    AUDIT_PRODUCT_ACTIVATED: "Producto activado",
    AUDIT_PRICE_CHANGED: "Cambio de precios",
    AUDIT_MOVEMENT: "Movimiento de inventario",
    AUDIT_SALES_REPORT: "Reporte de ventas generado",
    AUDIT_EXPENSE: "Gasto registrado",
    AUDIT_PAYROLL: "Pago de nómina",
    AUDIT_IMPORT: "Productos importados",
}


def log_audit(
    accion: str,
    modulo: str,
    detalle: str | None = None,
    usuario_rol: str | None = None,
    sede: str | None = None,
) -> None:
    """Best-effort audit record.

    Records an important action (login, product/price/inventory/expense/payroll
    changes, report generation) for the GERENCIA-only Auditoría view. This is a
    non-critical side effect: any failure is swallowed so it can NEVER break the
    primary action it is attached to.
    """
    try:
        with _get_conn() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO audit_log
                            (accion, modulo, detalle, usuario_rol, sede)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (accion, modulo, detalle, usuario_rol, sede),
                    )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
    except Exception:
        # Auditing must never interrupt the user's real action.
        pass


def list_audit(
    accion: str | None = None,
    modulo: str | None = None,
    date_from=None,
    date_to=None,
    limit: int = 500,
) -> list[dict]:
    """Return audit entries (newest first), optionally filtered."""
    clauses: list[str] = []
    params: list = []
    if accion:
        clauses.append("accion = %s")
        params.append(accion)
    if modulo:
        clauses.append("modulo = %s")
        params.append(modulo)
    if date_from is not None:
        clauses.append("created_at::date >= %s")
        params.append(date_from)
    if date_to is not None:
        clauses.append("created_at::date <= %s")
        params.append(date_to)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = (
        "SELECT id, accion, modulo, detalle, usuario_rol, sede, created_at "
        f"FROM audit_log {where} ORDER BY created_at DESC, id DESC LIMIT %s"
    )
    params.append(limit)
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


def list_audit_modules() -> list[str]:
    """Distinct module names present in the audit log (for filter options)."""
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT modulo FROM audit_log ORDER BY modulo"
            )
            return [r[0] for r in cur.fetchall()]


def add_comment(usuario_rol: str, sede: str | None, comentario: str) -> None:
    """Create a comment. Any role can call this; starts as 'pendiente'."""
    with _get_conn() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO comments (usuario_rol, sede, comentario, estado)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (usuario_rol, sede, comentario, COMMENT_PENDIENTE),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def list_comments(
    estado: str | None = None,
    limit: int = 500,
) -> list[dict]:
    """Return comments (newest first), optionally filtered by status."""
    clauses: list[str] = []
    params: list = []
    if estado:
        clauses.append("estado = %s")
        params.append(estado)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = (
        "SELECT id, usuario_rol, sede, comentario, estado, respuesta, "
        "respondido_por, respondido_at, created_at "
        f"FROM comments {where} ORDER BY created_at DESC, id DESC LIMIT %s"
    )
    params.append(limit)
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


def respond_comment(comment_id: int, respuesta: str, respondido_por: str) -> None:
    """Store a GERENCIA response for a comment (records who + when)."""
    with _get_conn() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE comments
                    SET respuesta = %s,
                        respondido_por = %s,
                        respondido_at = now()
                    WHERE id = %s
                    """,
                    (respuesta, respondido_por, comment_id),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def set_comment_status(comment_id: int, estado: str) -> None:
    """Change a comment's status (GERENCIA only, enforced by the view)."""
    if estado not in COMMENT_STATUS_LABELS:
        raise ValueError(f"Estado de comentario inválido: {estado}")
    with _get_conn() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE comments SET estado = %s WHERE id = %s",
                    (estado, comment_id),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


# --------------------------------------------------------------------------- #
# Solicitudes de reposición (replenishment / purchase requests)
# --------------------------------------------------------------------------- #

# Request status keys (stored on replenishment_requests.estado, CHECK-constrained).
REPO_PENDIENTE = "pendiente"
REPO_EN_PROCESO = "en_proceso"
REPO_COMPRADO = "comprado"
REPO_RECIBIDO = "recibido"
REPO_STATUS_LABELS = {
    REPO_PENDIENTE: "Pendiente",
    REPO_EN_PROCESO: "En proceso",
    REPO_COMPRADO: "Comprado",
    REPO_RECIBIDO: "Recibido",
}
# An "open" request is anything not yet fully received; used to avoid duplicates.
_REPO_OPEN_STATES = (REPO_PENDIENTE, REPO_EN_PROCESO, REPO_COMPRADO)


def add_replenishment_request(
    *,
    product_id: int | None,
    codigo: str | None,
    descripcion: str,
    sede: str,
    material_tipo: str | None,
    stock_actual,
    stock_minimo,
    cantidad_sugerida,
    solicitado_por: str,
) -> bool:
    """Create a replenishment (purchase) request for a product.

    Returns True when a new request is created, or False when the product
    already has an OPEN request (not yet 'recibido') — this prevents duplicates
    when the same alert is clicked repeatedly. This NEVER changes stock; it only
    records a purchase request.
    """
    with _get_conn() as conn:
        try:
            with conn.cursor() as cur:
                if product_id is not None:
                    cur.execute(
                        "SELECT 1 FROM replenishment_requests "
                        "WHERE product_id = %s AND estado = ANY(%s) LIMIT 1",
                        (product_id, list(_REPO_OPEN_STATES)),
                    )
                    if cur.fetchone():
                        conn.rollback()
                        return False
                cur.execute(
                    """
                    INSERT INTO replenishment_requests
                        (product_id, codigo, descripcion, sede, material_tipo,
                         stock_actual, stock_minimo, cantidad_sugerida,
                         solicitado_por, estado)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        product_id,
                        codigo,
                        descripcion,
                        sede,
                        material_tipo,
                        stock_actual,
                        stock_minimo,
                        cantidad_sugerida,
                        solicitado_por,
                        REPO_PENDIENTE,
                    ),
                )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise


def list_replenishment_requests(
    estado: str | None = None,
    limit: int = 500,
) -> list[dict]:
    """Return replenishment requests (newest first), optional status filter."""
    clauses: list[str] = []
    params: list = []
    if estado:
        clauses.append("estado = %s")
        params.append(estado)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = (
        "SELECT id, product_id, codigo, descripcion, sede, material_tipo, "
        "stock_actual, stock_minimo, cantidad_sugerida, solicitado_por, "
        "estado, created_at "
        f"FROM replenishment_requests {where} "
        "ORDER BY created_at DESC, id DESC LIMIT %s"
    )
    params.append(limit)
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


def set_replenishment_status(request_id: int, estado: str) -> None:
    """Change a request's status (GERENCIA only, enforced by the view)."""
    if estado not in REPO_STATUS_LABELS:
        raise ValueError(f"Estado de solicitud inválido: {estado}")
    with _get_conn() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE replenishment_requests SET estado = %s WHERE id = %s",
                    (estado, request_id),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def open_replenishment_product_ids(
    sede: str | None = None,
    material_tipo: str | None = None,
) -> set:
    """product_ids that currently have an OPEN (not 'recibido') request.

    Used by the ALERTAS view to show which products were already requested so it
    does not offer the button twice.
    """
    clauses = ["estado = ANY(%s)", "product_id IS NOT NULL"]
    params: list = [list(_REPO_OPEN_STATES)]
    if sede is not None:
        clauses.append("sede = %s")
        params.append(sede)
    if material_tipo is not None:
        clauses.append("material_tipo = %s")
        params.append(material_tipo)
    where = " AND ".join(clauses)
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT product_id FROM replenishment_requests "
                f"WHERE {where}",
                params,
            )
            return {r[0] for r in cur.fetchall()}
