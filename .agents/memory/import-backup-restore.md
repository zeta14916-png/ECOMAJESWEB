---
name: Import backup/restore reverts stock
description: What restore_products_backup rewinds and the intended tradeoff behind it
---

# Import backup/restore semantics (ECOMAJES)

`product_backups` is the safety net for GERENCIA's three importers (Productos/Precios/Stock).
`db.restore_products_backup(backup_id)` restores products **catalog fields AND `stock`/`stock_minimo`**, plus rebuilds the `prices` table, all in one transaction.

**Why:** Importar Stock overwrites `products.stock`, so restore had to rewind stock too — otherwise a bad stock import would be irreversible, contradicting the UI warning "se perderán todos los cambios posteriores a ese respaldo." (Before this feature, restore was catalog-only and deliberately left stock alone.)

**How to apply / caveat:** Restore rewinds stock to the snapshot value but does NOT rewind the `movements` ledger. So restoring long after a backup can make `products.stock` diverge from movement history. Treat restore as *immediate post-import recovery*, not a general time machine. If you ever need consistency, reconcile/rollback post-backup movements or block restore when they exist.
