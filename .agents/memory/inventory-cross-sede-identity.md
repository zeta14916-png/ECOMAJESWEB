---
name: Cross-sede product identity for combined inventory
description: How the same product held in two sedes is collapsed into one row without duplication, and why codigo can't be the key.
---

# Cross-sede product identity (combined inventory)

The `products` table stores one row per **(sede, material_tipo, nombre)** (that is
the unique constraint). The same physical product held in both Sede Principal and
Sucursal therefore exists as two separate rows.

**Rule:** when combining stock across sedes into a single row (e.g. Gestión de
Inventario / Empresa Completa), group by **(material_tipo, nombre)** — NOT by
`codigo`.

**Why:** `codigo` is *partial-unique when not null* (unique across the whole table),
so a product with a codigo can only appear in ONE sede row. Grouping by codigo would
never combine two sedes. `nombre` is the only field that is stable per-product and
repeats across sedes, so (material_tipo, nombre) is the correct cross-sede identity.

**How to apply:** in the combining query, split per-sede stock with
`SUM(stock) FILTER (WHERE sede = %s)`, take representative catalog fields
(codigo/descripcion/categoria/unidad/stock_minimo) via `MAX(...)`, and emit presence
flags `bool_or(sede = %s)` so a sede holding zero stock still counts when scoping the
view to that location. Estado is derived from the scope-relevant stock: `<=0` Agotado,
`<= stock_minimo` Stock bajo, else OK.
