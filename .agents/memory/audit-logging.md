---
name: ECOMAJES audit logging & identity model
description: How activity tracking (audit_log) is woven into ECOMAJES and why "user" equals "role"
---

# Audit logging in ECOMAJES

The AUDITORÍA module records activity across the app via `db.log_audit(accion, modulo, detalle, usuario_rol, sede=None)`.

**Rule:** `log_audit` is best-effort — it swallows ALL exceptions so it can never break the primary action it is instrumenting. Call it only at *success* points (after the DB write succeeded, before `st.rerun()`), never before.

**Why:** the user explicitly approved adding an invisible "record this action" step inside existing features, but only if it cannot break those features. A failed audit insert must be silent.

**How to apply:** when adding a new tracked action, define an `AUDIT_*` constant + label in `db.py`, then add one `db.log_audit(...)` at the success branch of the feature. For discrete UI events like downloads, attach it via the widget's `on_click` callback so it logs once per click, not once per render.

## Identity model
ECOMAJES logs in by ROLE only (OPERARIOS / ÁREA ADMINISTRATIVA / GERENCIA) — there is no per-user identity. So in every audit/comment record, "usuario" == "rol". Do not invent a user field; reuse `usuario_rol` (available as `ctx["usuario_rol"]`).

## Schema convention (gotcha)
New tables (`comments`, `audit_log`, etc.) are created directly in the DEV Postgres DB via SQL — there are NO migration files or startup DDL. Production schema is applied by Replit's Publish flow. Follow this existing pattern; do not add migration scripts.
