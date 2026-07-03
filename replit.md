# ECOMAJES

Python Streamlit application.

## Run & Operate

- `streamlit run app.py --server.port 5000` — run the ECOMAJES Streamlit app (workflow "Streamlit App", port 5000); entry point is `app.py`, config in `.streamlit/config.toml` (do not change server settings)
- `pnpm --filter @workspace/api-server run dev` — run the API server (port 5000)
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- Required env: `DATABASE_URL` — Postgres connection string

## Stack

- pnpm workspaces, Node.js 24, TypeScript 5.9
- API: Express 5
- DB: PostgreSQL + Drizzle ORM
- Validation: Zod (`zod/v4`), `drizzle-zod`
- API codegen: Orval (from OpenAPI spec)
- Build: esbuild (CJS bundle)

## Where things live

- `app.py` — entry point; wires session init, login gate, and navigation only
- `ecomajes/config.py` — source of truth for roles, sedes, and the navigation tree (`get_navigation(role, sede)`, `get_sedes(role)`); uses `Page` (leaf) and `Group` (sub-menu) dataclasses
- `ecomajes/auth.py` — password requirements per role (reads env vars `ECOMAJES_ADMIN_PASSWORD`, `ECOMAJES_GERENCIA_PASSWORD`)
- `ecomajes/session.py` — session-state helpers (login/logout, active page)
- `ecomajes/login.py` — login screen (role + sede + password); sede options depend on role
- `ecomajes/navigation.py` — role/sede-based sidebar (flat + grouped) + `ROUTES` table mapping page keys to real views; unlisted pages fall back to the placeholder
- `ecomajes/db.py` — PostgreSQL data layer (psycopg2 pool via `DATABASE_URL`); products + movements with atomic stock updates (`register_movement`, raises `StockError`)
- `ecomajes/views/inventario.py` — product list + add-product form (scoped by sede/material type)
- `ecomajes/views/movimientos.py` — register entrada/salida/venta (updates stock) + recent movements
- `ecomajes/views/precios.py` — mini-Excel price sheet (`st.data_editor`): edit + save prices per product; used automatically for future ventas
- `ecomajes/views/reporte_ventas.py` — sales report (page `adm_mn_reporte_ventas`): filter by period (Día/Semana/Mes/Año) + location (Principal/Sucursal/Empresa Completa); shows totals via `db.financial_summary`; add optional daily expenses + observations
- `ecomajes/views/balance.py` — Balance Financiero + Dashboard (page `ger_balance_financiero`, GERENCIA): single screen with filters (ubicación/rango de fechas/categoría), 8 KPI cards (ventas día/mes, gastos día/mes, utilidad neta, productos vendidos, stock bajo, agotados), charts (ventas por día/mes, productos más/menos vendidos, ventas por sede, ingresos vs gastos, inventario por categoría), and an alerts block (stock bajo, agotados, comentarios pendientes placeholder, últimos movimientos). KPI cards use the location filter with fixed día/mes periods; the date-range + category filters drive the charts. Reuses existing data only (venta movements, expenses, stock, prices) — no data duplication
- `ecomajes/views/_placeholder.py` — shared placeholder page for not-yet-built menu entries

## Data model

- `products` (id, sede, material_tipo ['nuevo'|'segundo_uso'], nombre, sku, unidad, stock, created_at); unique on (sede, material_tipo, nombre). Catálogo de productos fields also live here (products IS the inventory/catalog table): `codigo` (partial-unique when not null), `descripcion`, `categoria`, `tipo_venta` (CHECK-constrained: 'unidad'|'metro'|'centimetro'|'plancha_completa'|'corte_personalizado', default 'unidad'), `peso`, `stock_minimo` (>= 0, default 0), `observaciones`, `activo` (bool, default true = Estado activo/inactivo). `unidad` is the existing column reused for Unidad. Sale-type keys/labels are defined in `db.py` (`VENTA_*`, `TIPO_VENTA_LABELS`). Corte personalizado stores only the sale type + observaciones for now (no cutting calculations yet)
- `movements` (id, product_id→products, tipo ['entrada'|'salida'|'venta'], cantidad, nota, usuario_rol, sede, created_at, precio_unitario, precio_total); on `venta` the unit price is snapshotted from `prices` into `precio_unitario`/`precio_total`. Sales = venta movements (source of truth for the sales report)
- `prices` (id, product_id→products UNIQUE, codigo, descripcion, categoria, unidad, peso, precio, p1, p2, p3, precio_minimo, precio_sugerido, observaciones, created_at, updated_at); one row per product, upserted via `db.save_prices`
- `expenses` (id, fecha, descripcion, monto, sede, usuario_rol, created_at); daily expenses per location, feed `db.financial_summary` net-income and future Balance Financiero
- `daily_observations` (id, fecha, sede, observacion, usuario_rol, created_at); optional daily notes per location
- `db.financial_summary(sede, include_all_sedes, date_from, date_to)` — shared aggregate (total_sales, total_products, total_revenue, total_expenses, net_income); reusable by Balance Financiero later
- Stock is stored on `products.stock` and mutated only via `db.register_movement` inside a `SELECT … FOR UPDATE` transaction; entrada adds, salida/venta subtract, negative stock is rejected
- Schema is created in the dev DB via SQL; production schema is applied by Replit's Publish flow (do not write migration scripts or startup DDL)

## Architecture decisions

- Roles/sedes/modules and access are centralized in `config.py`; module→render mapping lives in `navigation.py` to keep `config.py` import-free (avoids circular deps)
- Auth is scaffolded (not yet hardened): passwords come from env vars with dev fallbacks. "Simple vs strong password" is currently expressed by the configured values, not an enforced strength policy
- GERENCIA selects a sede for data context but gets all modules regardless of sede

## Product

ERP for a steel & hardware company (acero y ferretería). Three roles — OPERARIOS (no password), ÁREA ADMINISTRATIVA (password), GERENCIA (password) — each with role/sede-scoped modules. Business logic per module is built incrementally, one module at a time, after approval.

## User preferences

_Populate as you build — explicit user instructions worth remembering across sessions._

## Gotchas

_Populate as you build — sharp edges, "always run X before Y" rules._

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
