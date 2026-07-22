-- ECOMAJES ERP — Migración FASE 2
-- Ejecutar en Railway (producción) o en la BD de desarrollo.
-- Todas las sentencias son idempotentes (IF NOT EXISTS / ADD COLUMN IF NOT EXISTS).

-- 1. Agregar metodo_pago a movements
ALTER TABLE movements
    ADD COLUMN IF NOT EXISTS metodo_pago text
        CHECK (metodo_pago IS NULL OR metodo_pago = ANY (ARRAY[
            'efectivo', 'yape', 'plin', 'transferencia', 'caja_chica'
        ]));

-- 2. Ingresos adicionales por día/sede
CREATE TABLE IF NOT EXISTS ingresos_adicionales (
    id          SERIAL PRIMARY KEY,
    fecha       date NOT NULL,
    descripcion text NOT NULL,
    monto       numeric(12,2) NOT NULL CHECK (monto >= 0),
    sede        text NOT NULL,
    usuario_rol text,
    created_at  timestamptz DEFAULT now() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ingresos_ad_fecha_sede
    ON ingresos_adicionales (fecha, sede);

-- 3. Deudores
CREATE TABLE IF NOT EXISTS deudores (
    id          SERIAL PRIMARY KEY,
    nombre      text NOT NULL,
    descripcion text NOT NULL DEFAULT '',
    monto       numeric(12,2) NOT NULL CHECK (monto >= 0),
    sede        text NOT NULL,
    estado      text NOT NULL DEFAULT 'pendiente'
                    CHECK (estado = ANY (ARRAY['pendiente', 'pagado'])),
    usuario_rol text,
    created_at  timestamptz DEFAULT now() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_deudores_estado ON deudores (estado);
CREATE INDEX IF NOT EXISTS idx_deudores_sede   ON deudores (sede);

-- 4. Entrega de sobres
CREATE TABLE IF NOT EXISTS entrega_sobres (
    id           SERIAL PRIMARY KEY,
    fecha        date NOT NULL,
    destinatario text NOT NULL,
    descripcion  text NOT NULL DEFAULT '',
    monto        numeric(12,2) NOT NULL CHECK (monto >= 0),
    sede         text NOT NULL,
    usuario_rol  text,
    created_at   timestamptz DEFAULT now() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_entrega_sobres_fecha_sede
    ON entrega_sobres (fecha, sede);

-- 5. Compras (registro de compra de productos — NO modifica precios/stock)
CREATE TABLE IF NOT EXISTS compras (
    id             SERIAL PRIMARY KEY,
    codigo         text,
    descripcion    text NOT NULL DEFAULT '',
    cantidad       numeric(14,3) NOT NULL DEFAULT 0,
    costo_unitario numeric(12,2) NOT NULL DEFAULT 0,
    costo_total    numeric(14,2) NOT NULL DEFAULT 0,
    proveedor      text,
    fecha          date,
    sede           text NOT NULL,
    usuario_rol    text,
    created_at     timestamptz DEFAULT now() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_compras_sede       ON compras (sede);
CREATE INDEX IF NOT EXISTS idx_compras_fecha_sede ON compras (fecha, sede);
CREATE INDEX IF NOT EXISTS idx_compras_codigo     ON compras (codigo);
