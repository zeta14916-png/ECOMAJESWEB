---
name: ECOMAJES ERP conventions
description: Durable build rules for the ECOMAJES ERP (steel & hardware, Streamlit).
---

**Build cadence (user rule):** build navigation/placeholders first, then implement module business logic ONE module at a time, waiting for explicit approval before each. Never add functionality ahead of approval.
**Why:** the user has repeatedly and explicitly required navigation-only scaffolding and per-module sign-off.
**How to apply:** when asked for a module, implement just that one, keep others as placeholders, and stop for approval before the next.

**Navigation source of truth:** `ecomajes/config.py` (`get_navigation`, `get_sedes`). All pages route through one shared placeholder — do NOT create per-page view files; extend the config tree instead.

**Consolidated views (Empresa Completa / all material types) can show two products with the same name/sede/unit.** Always key Streamlit selection widgets by the product `id` (format_func for display), never by the display label — label-keyed dicts silently collide and route a movement to the wrong row.

**Auth hardening is deferred:** "simple vs strong password" is expressed by configured env values, not an enforced strength policy. Dev fallback passwords exist and must be removed / fail-closed before production — only do this once the user approves the auth-hardening phase.
