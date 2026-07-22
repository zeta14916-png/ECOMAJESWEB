--
-- PostgreSQL database dump
--

\restrict 50tuNFgc2MqEghJq8hM1M00Ycji4bydUTiIqwo3BUbYsf9GYNYttFVO7F65rZFg

-- Dumped from database version 16.10
-- Dumped by pg_dump version 16.10

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_log (
    id integer NOT NULL,
    usuario_rol text,
    accion text NOT NULL,
    modulo text NOT NULL,
    detalle text,
    sede text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: audit_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.audit_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: audit_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.audit_log_id_seq OWNED BY public.audit_log.id;


--
-- Name: comments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.comments (
    id integer NOT NULL,
    usuario_rol text NOT NULL,
    sede text,
    comentario text NOT NULL,
    estado text DEFAULT 'pendiente'::text NOT NULL,
    respuesta text,
    respondido_por text,
    respondido_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT comments_estado_check CHECK ((estado = ANY (ARRAY['pendiente'::text, 'en_revision'::text, 'atendido'::text])))
);


--
-- Name: comments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.comments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: comments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.comments_id_seq OWNED BY public.comments.id;


--
-- Name: daily_observations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.daily_observations (
    id integer NOT NULL,
    fecha date NOT NULL,
    sede text NOT NULL,
    observacion text NOT NULL,
    usuario_rol text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: daily_observations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.daily_observations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: daily_observations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.daily_observations_id_seq OWNED BY public.daily_observations.id;


--
-- Name: employees; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.employees (
    id integer NOT NULL,
    nombre text NOT NULL,
    username text NOT NULL,
    password_hash text NOT NULL,
    password_salt text NOT NULL,
    rol text NOT NULL,
    estado text DEFAULT 'activo'::text NOT NULL,
    telefono text,
    direccion text,
    fecha_ingreso date,
    salario numeric(12,2) DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT employees_estado_check CHECK ((estado = ANY (ARRAY['activo'::text, 'inactivo'::text])))
);


--
-- Name: employees_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.employees_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: employees_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.employees_id_seq OWNED BY public.employees.id;


--
-- Name: expenses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.expenses (
    id integer NOT NULL,
    fecha date NOT NULL,
    descripcion text NOT NULL,
    monto numeric(12,2) NOT NULL,
    sede text NOT NULL,
    usuario_rol text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT expenses_monto_check CHECK ((monto >= (0)::numeric))
);


--
-- Name: expenses_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.expenses_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: expenses_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.expenses_id_seq OWNED BY public.expenses.id;


--
-- Name: movements; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.movements (
    id integer NOT NULL,
    product_id integer NOT NULL,
    tipo text NOT NULL,
    cantidad numeric(14,3) NOT NULL,
    nota text,
    usuario_rol text,
    sede text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    precio_unitario numeric(12,2),
    precio_total numeric(12,2),
    tipo_venta text,
    autorizado_por text,
    CONSTRAINT movements_cantidad_check CHECK ((cantidad > (0)::numeric)),
    CONSTRAINT movements_tipo_check CHECK ((tipo = ANY (ARRAY['entrada'::text, 'salida'::text, 'venta'::text]))),
    CONSTRAINT movements_tipo_venta_check CHECK (((tipo_venta IS NULL) OR (tipo_venta = ANY (ARRAY['unidad'::text, 'metro'::text, 'centimetro'::text, 'plancha_completa'::text, 'corte_personalizado'::text]))))
);


--
-- Name: movements_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.movements_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: movements_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.movements_id_seq OWNED BY public.movements.id;


--
-- Name: payroll_payments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payroll_payments (
    id integer NOT NULL,
    employee_id integer NOT NULL,
    fecha date NOT NULL,
    salario numeric(12,2) DEFAULT 0 NOT NULL,
    bono numeric(12,2) DEFAULT 0 NOT NULL,
    adelanto numeric(12,2) DEFAULT 0 NOT NULL,
    descuento numeric(12,2) DEFAULT 0 NOT NULL,
    pago_final numeric(12,2) NOT NULL,
    observacion text,
    usuario_rol text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: payroll_payments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.payroll_payments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: payroll_payments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.payroll_payments_id_seq OWNED BY public.payroll_payments.id;


--
-- Name: prices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.prices (
    id integer NOT NULL,
    product_id integer NOT NULL,
    codigo text,
    descripcion text,
    categoria text,
    unidad text,
    peso numeric(12,3),
    precio numeric(12,2),
    p1 numeric(12,2),
    p2 numeric(12,2),
    p3 numeric(12,2),
    precio_minimo numeric(12,2),
    precio_sugerido numeric(12,2),
    observaciones text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    costo numeric,
    venta_oficial numeric,
    venta_3m numeric,
    venta_metro numeric
);


--
-- Name: prices_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.prices_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: prices_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.prices_id_seq OWNED BY public.prices.id;


--
-- Name: product_backups; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.product_backups (
    id integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    import_mode text NOT NULL,
    product_count integer DEFAULT 0 NOT NULL,
    products_data jsonb DEFAULT '[]'::jsonb NOT NULL,
    prices_data jsonb DEFAULT '[]'::jsonb NOT NULL,
    restored_at timestamp with time zone
);


--
-- Name: product_backups_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.product_backups_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: product_backups_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.product_backups_id_seq OWNED BY public.product_backups.id;


--
-- Name: products; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.products (
    id integer NOT NULL,
    sede text NOT NULL,
    material_tipo text DEFAULT 'nuevo'::text NOT NULL,
    nombre text NOT NULL,
    sku text,
    unidad text DEFAULT 'unidad'::text NOT NULL,
    stock numeric(14,3) DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    codigo text,
    descripcion text,
    categoria text,
    tipo_venta text DEFAULT 'unidad'::text NOT NULL,
    peso numeric,
    stock_minimo numeric DEFAULT 0 NOT NULL,
    observaciones text,
    activo boolean DEFAULT true NOT NULL,
    familia text,
    CONSTRAINT products_stock_minimo_check CHECK ((stock_minimo >= (0)::numeric)),
    CONSTRAINT products_tipo_venta_check CHECK ((tipo_venta = ANY (ARRAY['unidad'::text, 'metro'::text, 'centimetro'::text, 'plancha_completa'::text, 'corte_personalizado'::text])))
);


--
-- Name: products_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.products_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: products_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.products_id_seq OWNED BY public.products.id;


--
-- Name: replenishment_requests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.replenishment_requests (
    id integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    product_id integer,
    codigo text,
    descripcion text NOT NULL,
    sede text NOT NULL,
    material_tipo text,
    stock_actual numeric DEFAULT 0 NOT NULL,
    stock_minimo numeric DEFAULT 0 NOT NULL,
    cantidad_sugerida numeric DEFAULT 0 NOT NULL,
    solicitado_por text NOT NULL,
    estado text DEFAULT 'pendiente'::text NOT NULL,
    CONSTRAINT replenishment_requests_estado_check CHECK ((estado = ANY (ARRAY['pendiente'::text, 'en_proceso'::text, 'comprado'::text, 'recibido'::text])))
);


--
-- Name: replenishment_requests_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.replenishment_requests_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: replenishment_requests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.replenishment_requests_id_seq OWNED BY public.replenishment_requests.id;


--
-- Name: audit_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log ALTER COLUMN id SET DEFAULT nextval('public.audit_log_id_seq'::regclass);


--
-- Name: comments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comments ALTER COLUMN id SET DEFAULT nextval('public.comments_id_seq'::regclass);


--
-- Name: daily_observations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.daily_observations ALTER COLUMN id SET DEFAULT nextval('public.daily_observations_id_seq'::regclass);


--
-- Name: employees id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employees ALTER COLUMN id SET DEFAULT nextval('public.employees_id_seq'::regclass);


--
-- Name: expenses id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expenses ALTER COLUMN id SET DEFAULT nextval('public.expenses_id_seq'::regclass);


--
-- Name: movements id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movements ALTER COLUMN id SET DEFAULT nextval('public.movements_id_seq'::regclass);


--
-- Name: payroll_payments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payroll_payments ALTER COLUMN id SET DEFAULT nextval('public.payroll_payments_id_seq'::regclass);


--
-- Name: prices id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prices ALTER COLUMN id SET DEFAULT nextval('public.prices_id_seq'::regclass);


--
-- Name: product_backups id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_backups ALTER COLUMN id SET DEFAULT nextval('public.product_backups_id_seq'::regclass);


--
-- Name: products id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.products ALTER COLUMN id SET DEFAULT nextval('public.products_id_seq'::regclass);


--
-- Name: replenishment_requests id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.replenishment_requests ALTER COLUMN id SET DEFAULT nextval('public.replenishment_requests_id_seq'::regclass);


--
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (id);


--
-- Name: comments comments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comments
    ADD CONSTRAINT comments_pkey PRIMARY KEY (id);


--
-- Name: daily_observations daily_observations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.daily_observations
    ADD CONSTRAINT daily_observations_pkey PRIMARY KEY (id);


--
-- Name: employees employees_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employees
    ADD CONSTRAINT employees_pkey PRIMARY KEY (id);


--
-- Name: employees employees_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employees
    ADD CONSTRAINT employees_username_key UNIQUE (username);


--
-- Name: expenses expenses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.expenses
    ADD CONSTRAINT expenses_pkey PRIMARY KEY (id);


--
-- Name: movements movements_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movements
    ADD CONSTRAINT movements_pkey PRIMARY KEY (id);


--
-- Name: payroll_payments payroll_payments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payroll_payments
    ADD CONSTRAINT payroll_payments_pkey PRIMARY KEY (id);


--
-- Name: prices prices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prices
    ADD CONSTRAINT prices_pkey PRIMARY KEY (id);


--
-- Name: prices prices_product_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prices
    ADD CONSTRAINT prices_product_id_key UNIQUE (product_id);


--
-- Name: product_backups product_backups_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_backups
    ADD CONSTRAINT product_backups_pkey PRIMARY KEY (id);


--
-- Name: products products_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_pkey PRIMARY KEY (id);


--
-- Name: products products_sede_material_tipo_nombre_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_sede_material_tipo_nombre_key UNIQUE (sede, material_tipo, nombre);


--
-- Name: replenishment_requests replenishment_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.replenishment_requests
    ADD CONSTRAINT replenishment_requests_pkey PRIMARY KEY (id);


--
-- Name: idx_audit_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_created_at ON public.audit_log USING btree (created_at DESC);


--
-- Name: idx_comments_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_comments_created_at ON public.comments USING btree (created_at DESC);


--
-- Name: idx_expenses_fecha_sede; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_expenses_fecha_sede ON public.expenses USING btree (fecha, sede);


--
-- Name: idx_movements_product; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_movements_product ON public.movements USING btree (product_id);


--
-- Name: idx_observations_fecha_sede; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_observations_fecha_sede ON public.daily_observations USING btree (fecha, sede);


--
-- Name: idx_payroll_employee; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_payroll_employee ON public.payroll_payments USING btree (employee_id);


--
-- Name: idx_payroll_fecha; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_payroll_fecha ON public.payroll_payments USING btree (fecha);


--
-- Name: idx_products_sede_tipo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_products_sede_tipo ON public.products USING btree (sede, material_tipo);


--
-- Name: idx_repo_estado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_repo_estado ON public.replenishment_requests USING btree (estado);


--
-- Name: products_codigo_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX products_codigo_key ON public.products USING btree (codigo) WHERE (codigo IS NOT NULL);


--
-- Name: movements movements_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movements
    ADD CONSTRAINT movements_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id) ON DELETE CASCADE;


--
-- Name: payroll_payments payroll_payments_employee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payroll_payments
    ADD CONSTRAINT payroll_payments_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(id);


--
-- Name: prices prices_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prices
    ADD CONSTRAINT prices_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id) ON DELETE CASCADE;


--
-- Name: replenishment_requests replenishment_requests_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.replenishment_requests
    ADD CONSTRAINT replenishment_requests_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id) ON DELETE SET NULL;


--
-- PostgreSQL database dump complete
--

\unrestrict 50tuNFgc2MqEghJq8hM1M00Ycji4bydUTiIqwo3BUbYsf9GYNYttFVO7F65rZFg

