---
name: products table is shared by inventory AND catalog
description: How nombre vs descripcion coexist on the single products table across the Inventario and Productos (catalog) views
---

# `products` is one table serving two views

The `products` table backs BOTH the Inventario view and the GERENCIA > Productos (catalog) view. It has `nombre` (NOT NULL, unique per `(sede, material_tipo, nombre)`) used by inventory, PLUS catalog columns (`codigo`, `descripcion`, `categoria`, `tipo_venta`, `peso`, `stock_minimo`, `observaciones`, `activo`).

**Rule (catalog CRUD):**
- On CREATE: seed `nombre` from `descripcion` (the catalog form has no name field, but `nombre` is NOT NULL + unique).
- On UPDATE: NEVER write `nombre` or `stock` — they belong to the inventory side; overwriting `nombre` with `descripcion` would rename/clobber an inventory product.
- `codigo` has a partial unique index (`products_codigo_key WHERE codigo IS NOT NULL`); duplicate non-null codigo raises UniqueViolation — catch and show a friendly message.

**Why:** the catalog and inventory are the same physical rows; keeping `nombre` stable on catalog edits prevents the two views from fighting over the same column.

**How to apply:** any future write to `products` from a catalog/pricing context should keep catalog fields separate from `nombre`/`stock`. Add catalog DB helpers additively (don't modify `list_products`/`add_product`, which inventory depends on).
