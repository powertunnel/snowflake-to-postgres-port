-- PostgreSQL schema for the Snowflake retail-analytics RAW layer
-- Translated from setup.sql (Snowflake) -> PostgreSQL 16.
-- Type mapping: INT->INTEGER, DECIMAL->NUMERIC, TIMESTAMP(_NTZ)->TIMESTAMP, TEXT/VARCHAR/BOOLEAN as-is.

CREATE SCHEMA IF NOT EXISTS raw;
SET search_path TO raw, public;

DROP TABLE IF EXISTS raw.order_items, raw.orders, raw.customers,
                     raw.product_reviews, raw.support_tickets, raw.product_catalog CASCADE;

CREATE TABLE raw.customers (
    customer_id        INTEGER PRIMARY KEY,
    first_name         VARCHAR(50),
    last_name          VARCHAR(50),
    email              VARCHAR(100),
    phone              VARCHAR(20),
    address            VARCHAR(200),
    city               VARCHAR(50),
    state              VARCHAR(2),
    zip_code           VARCHAR(10),
    registration_date  DATE,
    customer_segment   VARCHAR(20)
);

CREATE TABLE raw.orders (
    order_id         VARCHAR(36) PRIMARY KEY,
    customer_id      INTEGER,
    order_date       TIMESTAMP,
    order_status     VARCHAR(20),
    total_amount     NUMERIC(10, 2),
    discount_percent NUMERIC(5, 2),
    shipping_cost    NUMERIC(8, 2)
);

CREATE TABLE raw.order_items (
    order_item_id    VARCHAR(36) PRIMARY KEY,
    order_id         VARCHAR(36),
    product_id       INTEGER,
    product_name     VARCHAR(100),
    product_category VARCHAR(50),
    quantity         INTEGER,
    unit_price       NUMERIC(10, 2),
    line_total       NUMERIC(12, 2)
);

CREATE TABLE raw.product_catalog (
    product_id       INTEGER PRIMARY KEY,
    product_name     VARCHAR(100),
    product_category VARCHAR(50),
    description      TEXT,
    features         TEXT,
    price            NUMERIC(10, 2),
    stock_quantity   INTEGER
);

CREATE TABLE raw.product_reviews (
    review_id         INTEGER PRIMARY KEY,
    product_id        INTEGER,
    customer_id       INTEGER,
    review_date       DATE,
    rating            INTEGER,
    review_title      VARCHAR(200),
    review_text       TEXT,
    verified_purchase BOOLEAN
);

CREATE TABLE raw.support_tickets (
    ticket_id   INTEGER PRIMARY KEY,
    customer_id INTEGER,
    ticket_date TIMESTAMP,
    category    VARCHAR(50),
    priority    VARCHAR(20),
    subject     VARCHAR(200),
    description TEXT,
    resolution  TEXT,
    status      VARCHAR(20)
);
