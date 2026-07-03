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
- `ecomajes/config.py` — source of truth for roles, sedes, modules, and the access matrix (`get_available_modules`)
- `ecomajes/auth.py` — password requirements per role (reads env vars `ECOMAJES_ADMIN_PASSWORD`, `ECOMAJES_GERENCIA_PASSWORD`)
- `ecomajes/session.py` — session-state helpers (login/logout, active module)
- `ecomajes/login.py` — login screen (role + sede + password)
- `ecomajes/navigation.py` — role/sede-based sidebar and module routing
- `ecomajes/views/` — one placeholder per module; each exposes `render()`

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
