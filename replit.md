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
- ÁREA ADMINISTRATIVA navigation (in `config.py`): each material section has the same 5 items in this order — Registro de Movimiento (`movimientos`), Inventario (`inventario`), Reporte de Ventas (`reporte_ventas`), Historial (no view yet → placeholder), Gestión de Inventario (`productos`, create/edit/deactivate). Sede Principal shows Material Nuevo + Material Segundo Uso; Sucursal shows Material Nuevo only. No generic "Reportes" for ADMINISTRATIVA (Reportes is GERENCIA-only). Page keys: `adm_mn_*` / `adm_msu_*` (registro_movimiento/inventario/reporte_ventas/historial/gestion_inventario)
- `ecomajes/views/reporte_ventas.py` — sales report (pages `adm_mn_reporte_ventas`, `adm_msu_reporte_ventas`): filter by period (Día/Semana/Mes/Año) + location (Principal/Sucursal/Empresa Completa); shows totals via `db.financial_summary`; add optional daily expenses + observations
- `ecomajes/views/balance.py` — Balance Financiero + Dashboard (page `ger_balance_financiero`, GERENCIA): single screen with filters (ubicación/rango de fechas/categoría), 8 KPI cards (ventas día/mes, gastos día/mes, utilidad neta, productos vendidos, stock bajo, agotados), charts (ventas por día/mes, productos más/menos vendidos, ventas por sede, ingresos vs gastos, inventario por categoría), and an alerts block (stock bajo, agotados, comentarios pendientes placeholder, últimos movimientos). KPI cards use the location filter with fixed día/mes periods; the date-range + category filters drive the charts. Reuses existing data only (venta movements, expenses, stock, prices) — no data duplication
- `ecomajes/views/reportes.py` — Reportes module (page `ger_reportes`, GERENCIA): period-based reports (Día/Semana/Mes/Año) for Sede Principal / Sucursal / Empresa Completa + optional categoría. `_gather(f)` builds one report payload (KPIs + tables) reused by both the on-screen render and the exports (no duplication): total ventas/productos/ingresos/gastos/utilidad, movimientos del período (`db.list_movements_range`), stock bajo/agotados, más/menos vendidos, and chart tables (ventas por día/mes/sede, ingresos vs gastos, inventario por categoría). Reuses existing read-only db functions only
- `ecomajes/reporting.py` — export helpers `build_excel(report)` (multi-sheet .xlsx via pandas + openpyxl) and `build_pdf(report)` (landscape A4 via reportlab); pure formatting of a report payload, no DB access. Requires `openpyxl` + `reportlab` (in requirements.txt)
- `ecomajes/views/comentarios.py` — Comentarios module (pages `op_comentarios`, `adm_comentarios`, `ger_comentarios`; all roles). Any role creates a comment (fecha auto, usuario=rol, ámbito/ubicación, texto, estado default Pendiente). GERENCIA (detected via `ctx["usuario_rol"] == config.ROLE_GERENCIA`) additionally sees response + status controls (Pendiente/En revisión/Atendido). Uses `db.add_comment/list_comments/respond_comment/set_comment_status`
- `ecomajes/views/auditoria.py` — Auditoría module (page `ger_auditoria`, GERENCIA-only, read-only). Role-guarded view of the audit trail with filters (acción/módulo/rango de fechas). Columns: fecha, usuario, rol, acción, módulo, detalles. Uses `db.list_audit` + `db.list_audit_modules`
- `ecomajes/views/_placeholder.py` — shared placeholder page for not-yet-built menu entries
- Audit logging is woven into existing modules at success points via best-effort `db.log_audit(...)` (never raises): login (`login.py`), product create/edit/deactivate/activate (`productos.py`), price save (`precios.py`), inventory movement (`movimientos.py`), expense (`reporte_ventas.py`), payroll payment (`recursos_humanos.py`), and report download (`reportes.py`, via `download_button` `on_click` so it logs only on an actual click, not per render)

## Data model

- `products` (id, sede, material_tipo ['nuevo'|'segundo_uso'], nombre, sku, unidad, stock, created_at); unique on (sede, material_tipo, nombre). Catálogo de productos fields also live here (products IS the inventory/catalog table): `codigo` (partial-unique when not null), `descripcion`, `categoria`, `tipo_venta` (CHECK-constrained: 'unidad'|'metro'|'centimetro'|'plancha_completa'|'corte_personalizado', default 'unidad'), `peso`, `stock_minimo` (>= 0, default 0), `observaciones`, `activo` (bool, default true = Estado activo/inactivo). `unidad` is the existing column reused for Unidad. Sale-type keys/labels are defined in `db.py` (`VENTA_*`, `TIPO_VENTA_LABELS`). Corte personalizado stores only the sale type + observaciones for now (no cutting calculations yet)
- `movements` (id, product_id→products, tipo ['entrada'|'salida'|'venta'], cantidad, nota, usuario_rol, sede, created_at, precio_unitario, precio_total); on `venta` the unit price is snapshotted from `prices` into `precio_unitario`/`precio_total`. Sales = venta movements (source of truth for the sales report)
- `prices` (id, product_id→products UNIQUE, codigo, descripcion, categoria, unidad, peso, precio, p1, p2, p3, precio_minimo, precio_sugerido, observaciones, created_at, updated_at); one row per product, upserted via `db.save_prices`
- `expenses` (id, fecha, descripcion, monto, sede, usuario_rol, created_at); daily expenses per location, feed `db.financial_summary` net-income and future Balance Financiero
- `daily_observations` (id, fecha, sede, observacion, usuario_rol, created_at); optional daily notes per location
- `comments` (id, created_at, usuario_rol, ambito/ubicación, texto, estado ['pendiente'|'en_revision'|'atendido'], respuesta, respondido_por, respondido_at); status labels/constants in `db.py` (`COMMENT_*`, `COMMENT_STATUS_LABELS`). Any role inserts; only GERENCIA sets `respuesta`/`estado`
- `audit_log` (id, created_at, usuario_rol, accion, modulo, detalle); append-only activity trail. Action keys/labels in `db.py` (`AUDIT_*`, `AUDIT_ACTION_LABELS`). Written only through best-effort `db.log_audit` (swallows all exceptions so it can never break the primary action). Read via `db.list_audit(accion, modulo, date_from, date_to)` + `db.list_audit_modules()`. Since login is by role (no per-user identity), `usuario` == `rol`
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
