-- Row-Level Security port of the Snowflake Row Access Policy
-- (setup.sql: customers_region_policy on raw.customers.state).
-- Snowflake semantics:
--   ADMIN roles           -> all rows
--   WEST_COAST_MANAGER    -> only CA, OR, WA
--   everyone else         -> no rows
-- Postgres mapping: table-owner bypass == admin "see all"; a SELECT policy
-- granted TO the west_coast_manager role == the CA/OR/WA branch; RLS default
-- deny for any other (non-owner, non-bypass) role == the ELSE FALSE branch.

-- 1. The restricted role (LOGIN so you can also connect directly as it)
DROP POLICY IF EXISTS customers_region_policy ON raw.customers;
DROP ROLE IF EXISTS west_coast_manager;
CREATE ROLE west_coast_manager LOGIN;

GRANT CONNECT ON DATABASE snowport TO west_coast_manager;
GRANT USAGE  ON SCHEMA raw         TO west_coast_manager;
GRANT SELECT ON ALL TABLES IN SCHEMA raw TO west_coast_manager;

-- 2. Turn on RLS for the customers table.
--    The table owner (sandbox) bypasses RLS automatically -> "admin sees all".
ALTER TABLE raw.customers ENABLE ROW LEVEL SECURITY;

-- 3. The region policy: west_coast_manager sees only CA/OR/WA.
CREATE POLICY customers_region_policy ON raw.customers
    FOR SELECT
    TO west_coast_manager
    USING (state IN ('CA', 'OR', 'WA'));
