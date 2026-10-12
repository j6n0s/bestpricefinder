-- 0001_init.sql — bestpricefinder base schema.
-- Applied by bpf.migrate as bpf_migrator, which runs `SET ROLE bpf_owner` first, so bpf_owner owns every object.
-- The roles bpf_owner, bpf_migrator, bpf_ingest and bpf_api are created by deploy/local/db-init.sh.
--
-- Schemas:
--   core = GVH Árfigyelő reference + daily price data (append-only history)
--   app  = our own content (ingredient ontology, recipes, KSH fallback prices, nutrition)
--   ops  = ingest bookkeeping
--   api  = read-only views; the ONLY schema the API role can see

CREATE SCHEMA core;
CREATE SCHEMA app;
CREATE SCHEMA ops;
CREATE SCHEMA api;

-- ───────────────────────── core: reference data ─────────────────────────

CREATE TABLE core.chain (
    id          text PRIMARY KEY CHECK (length(id) BETWEEN 1 AND 64),          -- GVH chain uuid
    name        text NOT NULL CHECK (length(name) BETWEEN 1 AND 100),
    slug        text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9-]{1,30}$'),
    is_grocery  boolean NOT NULL
);

CREATE TABLE core.store (
    id             text PRIMARY KEY CHECK (id ~ '^[A-Za-z0-9_-]{1,40}$'),     -- e.g. spar-110, aldi-J179
    chain_id       text NOT NULL REFERENCES core.chain(id),
    postal_code    text CHECK (postal_code ~ '^[0-9]{4}$'),
    city           text CHECK (length(city) <= 100),
    address        text CHECK (length(address) <= 200),
    lat            double precision CHECK (lat BETWEEN 45.0 AND 49.0),
    lon            double precision CHECK (lon BETWEEN 15.5 AND 23.5),
    opening_raw    text CHECK (length(opening_raw) <= 500),
    format         text CHECK (format IN ('hyper', 'express', 'other')),       -- inferred (Tesco id ranges); NULL = unknown
    is_budapest    boolean GENERATED ALWAYS AS (coalesce(postal_code ~ '^1[0-9]{3}$', false)) STORED,
    first_seen     date NOT NULL,
    last_seen      date NOT NULL,
    has_data_date  date                                                         -- last data_date with any product at this store
);
CREATE INDEX store_chain_idx ON core.store (chain_id);
CREATE INDEX store_budapest_idx ON core.store (is_budapest) WHERE is_budapest;

CREATE TABLE core.category (
    id         integer PRIMARY KEY,
    parent_id  integer REFERENCES core.category(id),
    name       text NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
    path       text NOT NULL CHECK (length(path) <= 300),
    level      smallint NOT NULL CHECK (level BETWEEN 1 AND 5),
    is_leaf    boolean NOT NULL,
    is_food    boolean NOT NULL
);
CREATE INDEX category_parent_idx ON core.category (parent_id);

CREATE TABLE core.product (
    id           text PRIMARY KEY CHECK (id ~ '^[A-Za-z0-9_.-]{1,64}$'),     -- EAN-13, in-store code, or lidl-/aldi-/penny- id
    name         text NOT NULL CHECK (length(name) BETWEEN 1 AND 300),
    category_id  integer NOT NULL REFERENCES core.category(id),
    unit         text NOT NULL CHECK (unit ~ '^[a-z]{1,10}$'),                -- kg | l | db (others rejected by ingest)
    unit_title   text CHECK (length(unit_title) <= 20),
    packaging    numeric(12,4) CHECK (packaging > 0),                           -- pack size in `unit`
    bulk         boolean,
    first_seen   date NOT NULL,
    last_seen    date NOT NULL
);
CREATE INDEX product_category_idx ON core.product (category_id);

-- ───────────────────────── core: daily prices (append-only history) ─────────────────────────

-- One row per product × chain × day. Prices in HUF (gross). *_unit = HUF per product.unit.
CREATE TABLE core.product_chain_day (
    data_date              date NOT NULL,
    product_id             text NOT NULL REFERENCES core.product(id),
    chain_id               text NOT NULL REFERENCES core.chain(id),
    product_min_amount     numeric(12,2) CHECK (product_min_amount >= 0),  -- price charged by ≥80% of carrying stores (what GVH shows)
    price_same_everywhere  boolean,
    normal_amount          numeric(12,2) CHECK (normal_amount >= 0),       -- listing prices[] = MIN across stores per type
    normal_unit            numeric(14,4) CHECK (normal_unit >= 0),
    discounted_amount      numeric(12,2) CHECK (discounted_amount >= 0),
    discounted_unit        numeric(14,4) CHECK (discounted_unit >= 0),
    loyalty_amount         numeric(12,2) CHECK (loyalty_amount >= 0),
    loyalty_unit           numeric(14,4) CHECK (loyalty_unit >= 0),
    xlsx_min               numeric(12,2) CHECK (xlsx_min >= 0),            -- official daily XLSX (daily price incl. DISCOUNTED, excl. LOYALTY)
    xlsx_max               numeric(12,2) CHECK (xlsx_max >= 0),
    xlsx_min_unit          numeric(14,4) CHECK (xlsx_min_unit >= 0),
    xlsx_max_unit          numeric(14,4) CHECK (xlsx_max_unit >= 0),
    stores_carrying        integer CHECK (stores_carrying >= 0),
    chain_store_count      integer CHECK (chain_store_count >= 0),
    PRIMARY KEY (data_date, product_id, chain_id)
);
CREATE INDEX pcd_product_hist_idx ON core.product_chain_day (product_id, chain_id, data_date);

-- Per-store prices, fetched only where a chain's price varies by store (XLSX min < max).
CREATE TABLE core.store_price_day (
    data_date          date NOT NULL,
    product_id         text NOT NULL REFERENCES core.product(id),
    store_id           text NOT NULL REFERENCES core.store(id),
    normal_amount      numeric(12,2) CHECK (normal_amount >= 0),
    normal_unit        numeric(14,4) CHECK (normal_unit >= 0),
    discounted_amount  numeric(12,2) CHECK (discounted_amount >= 0),
    discounted_unit    numeric(14,4) CHECK (discounted_unit >= 0),
    loyalty_amount     numeric(12,2) CHECK (loyalty_amount >= 0),
    loyalty_unit       numeric(14,4) CHECK (loyalty_unit >= 0),
    PRIMARY KEY (data_date, product_id, store_id)
);
CREATE INDEX spd_store_idx ON core.store_price_day (data_date, store_id);

-- Which stores carry a product (from /product/{id} availableInShops), one row per refresh.
CREATE TABLE core.product_availability (
    product_id  text NOT NULL REFERENCES core.product(id),
    as_of       date NOT NULL,
    chain_id    text NOT NULL REFERENCES core.chain(id),
    store_ids   text[] NOT NULL,
    PRIMARY KEY (product_id, chain_id, as_of)
);

-- History protection: rows for past days can never be rewritten or deleted by app roles.
-- (Today and yesterday stay correctable so a re-run of the daily ingest is idempotent.)
CREATE FUNCTION core.forbid_history_rewrite() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    cutoff date := (now() AT TIME ZONE 'Europe/Budapest')::date - 1;
    d date;
BEGIN
    IF TG_TABLE_NAME = 'product_availability' THEN
        d := OLD.as_of;
    ELSE
        d := OLD.data_date;
    END IF;
    IF d < cutoff THEN
        RAISE EXCEPTION 'history is append-only: % row for % cannot be %', TG_TABLE_NAME, d, lower(TG_OP)
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER pcd_append_only BEFORE UPDATE OR DELETE ON core.product_chain_day
    FOR EACH ROW EXECUTE FUNCTION core.forbid_history_rewrite();
CREATE TRIGGER spd_append_only BEFORE UPDATE OR DELETE ON core.store_price_day
    FOR EACH ROW EXECUTE FUNCTION core.forbid_history_rewrite();
CREATE TRIGGER pa_append_only BEFORE UPDATE OR DELETE ON core.product_availability
    FOR EACH ROW EXECUTE FUNCTION core.forbid_history_rewrite();

-- ───────────────────────── ops ─────────────────────────

CREATE TABLE ops.ingest_run (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kind         text NOT NULL CHECK (kind IN ('daily', 'availability', 'reference', 'content')),
    status       text NOT NULL CHECK (status IN ('running', 'ok', 'partial', 'failed')),
    started_at   timestamptz NOT NULL DEFAULT now(),
    finished_at  timestamptz,
    data_date    date,
    requests     integer NOT NULL DEFAULT 0 CHECK (requests >= 0),
    bytes        bigint NOT NULL DEFAULT 0 CHECK (bytes >= 0),
    warnings     jsonb NOT NULL DEFAULT '[]'::jsonb,
    stats        jsonb NOT NULL DEFAULT '{}'::jsonb,
    error        text
);
CREATE INDEX ingest_run_latest_idx ON ops.ingest_run (kind, status, data_date DESC);

-- ───────────────────────── app: our own content ─────────────────────────

CREATE TABLE app.ingredient (
    id               text PRIMARY KEY CHECK (id ~ '^[a-z0-9_]{2,40}$'),
    name_hu          text NOT NULL CHECK (length(name_hu) BETWEEN 1 AND 80),
    list_group       text NOT NULL CHECK (list_group ~ '^[a-z_]{2,30}$'),     -- shopping-list section
    unit             text NOT NULL CHECK (unit IN ('kg', 'l', 'db')),         -- canonical unit for quantities
    piece_weight_kg  numeric(8,4) CHECK (piece_weight_kg > 0),                 -- for db↔kg conversion
    pantry           boolean NOT NULL DEFAULT false,                           -- "valószínűleg otthon van"; never priced
    leaf_ids         integer[] NOT NULL DEFAULT '{}',                          -- GVH leaf categories
    include_patterns text[] NOT NULL DEFAULT '{}',                             -- case-insensitive regexes, ANY must match (if non-empty)
    exclude_patterns text[] NOT NULL DEFAULT '{}',                             -- case-insensitive regexes, NONE may match
    product_units    text[] NOT NULL DEFAULT '{}',                             -- allowed GVH product units ('kg','l','db'); empty = any convertible
    ksh_code         text CHECK (ksh_code ~ '^[0-9A-Za-z.-]{1,20}$'),          -- KSH ara0044 fallback
    nutrition_code   text CHECK (length(nutrition_code) <= 40),                -- app.nutrition.code
    notes            text CHECK (length(notes) <= 500)
);

CREATE TABLE app.recipe (
    id          text PRIMARY KEY CHECK (id ~ '^[a-z0-9-]{2,60}$'),
    title       text NOT NULL CHECK (length(title) BETWEEN 2 AND 120),
    summary     text CHECK (length(summary) <= 400),
    slots       text[] NOT NULL CHECK (cardinality(slots) >= 1 AND slots <@ ARRAY['reggeli','tizorai','ebed','uzsonna','vacsora']::text[]),
    servings    smallint NOT NULL CHECK (servings BETWEEN 1 AND 12),
    minutes     smallint CHECK (minutes BETWEEN 1 AND 600),
    tags        text[] NOT NULL DEFAULT '{}',
    steps       text[] NOT NULL CHECK (cardinality(steps) >= 1),
    tested      boolean NOT NULL DEFAULT false,                                -- cook-tested by a human
    source      text NOT NULL DEFAULT 'original' CHECK (source IN ('original')),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE app.recipe_line (
    recipe_id      text NOT NULL REFERENCES app.recipe(id) ON DELETE CASCADE,
    line_no        smallint NOT NULL CHECK (line_no BETWEEN 1 AND 60),
    ingredient_id  text NOT NULL REFERENCES app.ingredient(id),
    qty            numeric(10,3) NOT NULL CHECK (qty > 0),                      -- in the ingredient's canonical unit
    display        text NOT NULL CHECK (length(display) BETWEEN 1 AND 80),      -- e.g. "2 ek", "1 közepes fej"
    optional       boolean NOT NULL DEFAULT false,
    PRIMARY KEY (recipe_id, line_no)
);
CREATE INDEX recipe_line_ingredient_idx ON app.recipe_line (ingredient_id);

-- KSH STADAT ara0044 national average consumer prices (CC BY 4.0, "Forrás: KSH").
CREATE TABLE app.ksh_price (
    period  date NOT NULL,                                                      -- first day of month
    code    text NOT NULL CHECK (code ~ '^[0-9A-Za-z.-]{1,20}$'),
    name    text NOT NULL CHECK (length(name) <= 200),
    unit    text NOT NULL CHECK (length(unit) <= 20),                           -- as published, e.g. 'kg', 'l', 'db'
    price   numeric(12,2) NOT NULL CHECK (price >= 0),
    PRIMARY KEY (period, code)
);

-- Nutrient composition per 100 g (CIQUAL / Frida / USDA; source recorded per row).
CREATE TABLE app.nutrition (
    code       text PRIMARY KEY CHECK (length(code) BETWEEN 1 AND 40),
    source     text NOT NULL CHECK (source IN ('ciqual', 'frida', 'usda')),
    name       text NOT NULL CHECK (length(name) <= 200),
    kcal       numeric(8,2) CHECK (kcal >= 0),
    protein_g  numeric(8,2) CHECK (protein_g >= 0),
    carb_g     numeric(8,2) CHECK (carb_g >= 0),
    sugar_g    numeric(8,2) CHECK (sugar_g >= 0),
    fat_g      numeric(8,2) CHECK (fat_g >= 0),
    satfat_g   numeric(8,2) CHECK (satfat_g >= 0),
    fiber_g    numeric(8,2) CHECK (fiber_g >= 0),
    salt_g     numeric(8,2) CHECK (salt_g >= 0)
);
ALTER TABLE app.ingredient
    ADD CONSTRAINT ingredient_nutrition_fk FOREIGN KEY (nutrition_code) REFERENCES app.nutrition(code);

-- ───────────────────────── api: read-only views (the API role sees only these) ─────────────────────────

CREATE VIEW api.latest AS
SELECT max(data_date) AS data_date, max(finished_at) AS ingested_at
FROM ops.ingest_run
WHERE kind = 'daily' AND status IN ('ok', 'partial');

CREATE VIEW api.chain AS
SELECT id, name, slug, is_grocery FROM core.chain;

CREATE VIEW api.store AS
SELECT s.id, s.chain_id, c.slug AS chain_slug, c.name AS chain_name, c.is_grocery,
       s.postal_code, s.city, s.address, s.lat, s.lon, s.format, s.is_budapest,
       s.has_data_date, s.opening_raw
FROM core.store s JOIN core.chain c ON c.id = s.chain_id;

CREATE VIEW api.category AS
SELECT id, parent_id, name, path, level, is_leaf, is_food FROM core.category;

CREATE VIEW api.product AS
SELECT id, name, category_id, unit, unit_title, packaging, bulk, last_seen FROM core.product;

CREATE VIEW api.product_chain_latest AS
SELECT d.*
FROM core.product_chain_day d
WHERE d.data_date = (SELECT data_date FROM api.latest);

CREATE VIEW api.product_chain_history AS
SELECT data_date, product_id, chain_id, product_min_amount, normal_unit, discounted_unit, loyalty_unit
FROM core.product_chain_day;

CREATE VIEW api.store_price_latest AS
SELECT p.*
FROM core.store_price_day p
WHERE p.data_date = (SELECT data_date FROM api.latest);

CREATE VIEW api.product_availability_latest AS
SELECT DISTINCT ON (product_id, chain_id) product_id, chain_id, as_of, store_ids
FROM core.product_availability
ORDER BY product_id, chain_id, as_of DESC;

CREATE VIEW api.ingredient AS
SELECT id, name_hu, list_group, unit, piece_weight_kg, pantry, leaf_ids, include_patterns,
       exclude_patterns, product_units, ksh_code, nutrition_code
FROM app.ingredient;

CREATE VIEW api.recipe AS
SELECT id, title, summary, slots, servings, minutes, tags, steps, tested, updated_at FROM app.recipe;

CREATE VIEW api.recipe_line AS
SELECT recipe_id, line_no, ingredient_id, qty, display, optional FROM app.recipe_line;

CREATE VIEW api.ksh_latest AS
SELECT DISTINCT ON (code) period, code, name, unit, price
FROM app.ksh_price
ORDER BY code, period DESC;

CREATE VIEW api.nutrition AS
SELECT code, source, name, kcal, protein_g, carb_g, sugar_g, fat_g, satfat_g, fiber_g, salt_g FROM app.nutrition;

-- ───────────────────────── privileges (least privilege) ─────────────────────────

REVOKE ALL ON SCHEMA core, app, ops, api FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA core, app, ops, api FROM PUBLIC;
REVOKE ALL ON FUNCTION core.forbid_history_rewrite() FROM PUBLIC;

-- API: read-only, views only.
GRANT USAGE ON SCHEMA api TO bpf_api;
GRANT SELECT ON ALL TABLES IN SCHEMA api TO bpf_api;

-- Ingest: write data, never DDL, never rewrite history (trigger above), no access to api role's surface needed.
GRANT USAGE ON SCHEMA core, app, ops TO bpf_ingest;
GRANT SELECT, INSERT, UPDATE ON core.chain, core.store, core.category, core.product TO bpf_ingest;
GRANT SELECT, INSERT, UPDATE ON core.product_chain_day, core.store_price_day, core.product_availability TO bpf_ingest;
GRANT SELECT, INSERT, UPDATE ON ops.ingest_run TO bpf_ingest;
GRANT SELECT, INSERT, UPDATE, DELETE ON app.ingredient, app.recipe, app.recipe_line, app.ksh_price, app.nutrition TO bpf_ingest;
GRANT USAGE ON SCHEMA api TO bpf_ingest;
GRANT SELECT ON api.latest TO bpf_ingest;
