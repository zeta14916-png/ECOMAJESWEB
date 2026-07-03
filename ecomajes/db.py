"""Database access layer for ECOMAJES ERP.

Thin, dependency-light data access using psycopg2 against the Replit-managed
PostgreSQL database (connection string in the DATABASE_URL env var). A small
connection pool is cached for the Streamlit session.

Only the data operations needed by the current step live here: products
(inventory) and movements (entrada / salida / venta) with atomic stock updates.
"""

import os
from contextlib import contextmanager
from decimal import Decimal

import psycopg2
import psycopg2.extras
import psycopg2.pool
import streamlit as st

TIPO_NUEVO = "nuevo"
TIPO_SEGUNDO_USO = "segundo_uso"

MOVEMENT_ENTRADA = "entrada"
MOVEMENT_SALIDA = "salida"
MOVEMENT_VENTA = "venta"

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
) -> Decimal:
    """Register a movement and update the product stock atomically.

    Returns the resulting stock. Raises StockError for an unknown product or
    when a salida/venta would drive stock negative.
    """
    if tipo not in _ADDS_STOCK | _REMOVES_STOCK:
        raise StockError(f"Tipo de movimiento inválido: {tipo}")

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

                # For sales, snapshot the configured unit price so future
                # sales and movement reports use it automatically.
                precio_unitario = None
                precio_total = None
                if tipo == MOVEMENT_VENTA:
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
                         precio_unitario, precio_total)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
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
                    ),
                )
            conn.commit()
            return new_stock
        except Exception:
            conn.rollback()
            raise


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
