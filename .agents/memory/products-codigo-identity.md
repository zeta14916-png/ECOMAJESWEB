---
name: products.codigo is the global identity key
description: How product upserts/imports must key off codigo, and the nombre-uniqueness trap
---

`products.codigo` has a **partial-unique index** (`products_codigo_key ON codigo WHERE codigo IS NOT NULL`) — it is unique **globally across all sedes**, not per-sede. So a código identifies exactly one product regardless of sede/material_tipo.

There is a **second** unique constraint: `(sede, material_tipo, nombre)`. Catalog/import code seeds `nombre` from `descripcion`, so two different códigos sharing the same DESCRIPCION collide on this constraint even though their códigos differ.

**How to apply (imports/upserts):**
- Match/update by `codigo` (works across sedes). Only fall back to matching by `nombre` within `(sede, material_tipo)` when código is absent.
- On INSERT with nombre=descripcion, guard the `(sede,material_tipo,nombre)` collision — e.g. append ` (codigo)` to nombre — or the insert fails.
- Use a per-row SAVEPOINT in batch imports so one failing row doesn't roll back the whole batch.

**Why:** learned building the Excel importer — keying on sede+nombre would wrongly duplicate products that already exist under a different sede, and naive inserts blew up on the nombre uniqueness constraint.
