-- MetricMind governed warehouse schema (Postgres).
-- Executed automatically by the postgres image on first boot
-- (files in /docker-entrypoint-initdb.d run alphabetically).

DROP TABLE IF EXISTS orders, customer_quarters, customers, regions CASCADE;

CREATE TABLE regions (
    region_code   TEXT PRIMARY KEY,
    region_name   TEXT NOT NULL,
    continent     TEXT NOT NULL,
    margin_target NUMERIC(6, 3) NOT NULL
);

CREATE TABLE customers (
    customer_id   TEXT PRIMARY KEY,
    customer_name TEXT NOT NULL,
    segment       TEXT NOT NULL,
    region_code   TEXT NOT NULL REFERENCES regions (region_code),
    market        TEXT NOT NULL,
    country       TEXT NOT NULL,
    signup_date   DATE NOT NULL
);

CREATE TABLE orders (
    order_id      TEXT PRIMARY KEY,
    order_date    DATE NOT NULL,
    customer_id   TEXT NOT NULL REFERENCES customers (customer_id),
    region_code   TEXT NOT NULL REFERENCES regions (region_code),
    market        TEXT NOT NULL,
    category      TEXT NOT NULL,
    channel       TEXT NOT NULL,
    quantity      INTEGER NOT NULL,
    unit_price    NUMERIC(12, 2) NOT NULL,
    discount_pct  NUMERIC(6, 4) NOT NULL,
    order_amount  NUMERIC(14, 2) NOT NULL,
    cogs          NUMERIC(14, 2) NOT NULL
);

-- Retention facts: one row per customer per quarter (drives governed churn).
CREATE TABLE customer_quarters (
    customer_id          TEXT NOT NULL REFERENCES customers (customer_id),
    quarter_start        DATE NOT NULL,
    quarter_label        TEXT NOT NULL,
    active_last_quarter  SMALLINT NOT NULL,
    active_this_quarter  SMALLINT NOT NULL,
    churned              SMALLINT NOT NULL,
    PRIMARY KEY (customer_id, quarter_start)
);

CREATE INDEX orders_order_date_idx ON orders (order_date);
CREATE INDEX orders_region_code_idx ON orders (region_code);
CREATE INDEX orders_category_idx ON orders (category);
CREATE INDEX customers_region_code_idx ON customers (region_code);
