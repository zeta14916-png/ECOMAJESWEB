---
name: precio_sugerido must track precio
description: Why the Precios editor mirrors precio_sugerido = precio, and why product import must not write prices.
---

# precio_sugerido must track precio

The Precios editor (`ecomajes/views/precios.py`) has NO separate "precio sugerido"
column, but on every save it sets `precio_sugerido = precio` before calling
`db.save_prices`. `precio_sugerido` is kept in `db.PRICE_FIELDS` for this reason.

**Why:** `movimientos._suggested_unit_price` prefers `precio_sugerido` over `precio`
(`price.get("precio_sugerido") or price.get("precio")`). If a stored
`precio_sugerido` is left stale, editing "Precio en dólares" in Precios would NOT
change the price ventas actually suggest. Mirroring keeps ventas consistent with
the maintained price without touching the movements module.

**How to apply:** Any new price-write path into `prices` should either set
`precio_sugerido` alongside `precio`, or deliberately leave it NULL (movimientos
falls back to `precio` when it is NULL). Do not reintroduce a code path that sets
`precio_sugerido` to a value that can drift from `precio` unless the UI exposes it.

## Pricing is maintained ONLY in Precios (GERENCIA-only)
Per explicit product decision, no importer writes prices/cost. Importar Productos
was stripped of its precio/costo handling; the "Importar Precios" module was
removed entirely. Prices live only in the Precios editor, editable only by
GERENCIA. Don't add price/cost writes back into any importer.
