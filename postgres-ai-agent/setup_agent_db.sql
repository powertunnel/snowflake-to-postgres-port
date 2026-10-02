-- Database objects the AI agent depends on. Idempotent. Run as a superuser:
--   psql -d snowport -f setup_agent_db.sql
-- (Assumes the RAW tables + the RLS policy from rls.sql already exist.)

-- 1) "Search service": stored tsvector + GIN index over customer feedback.
ALTER TABLE raw.product_reviews
  ADD COLUMN IF NOT EXISTS search_tsv tsvector
  GENERATED ALWAYS AS (
    to_tsvector('english', coalesce(review_title,'') || ' ' || coalesce(review_text,''))
  ) STORED;
CREATE INDEX IF NOT EXISTS idx_reviews_tsv ON raw.product_reviews USING gin(search_tsv);

ALTER TABLE raw.support_tickets
  ADD COLUMN IF NOT EXISTS search_tsv tsvector
  GENERATED ALWAYS AS (
    to_tsvector('english', coalesce(subject,'') || ' ' || coalesce(description,'') || ' ' || coalesce(resolution,''))
  ) STORED;
CREATE INDEX IF NOT EXISTS idx_tickets_tsv ON raw.support_tickets USING gin(search_tsv);

-- 2) analyst_ro — the agent's default identity: read-only, sees ALL rows.
--    BYPASSRLS makes it the "admin" equivalent despite RLS on raw.customers.
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='analyst_ro') THEN
    CREATE ROLE analyst_ro LOGIN;
  END IF;
END $$;
ALTER ROLE analyst_ro BYPASSRLS;
GRANT CONNECT ON DATABASE snowport TO analyst_ro;
GRANT USAGE  ON SCHEMA raw, dbt_staging, dbt_intermediate, dbt_analytics TO analyst_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA raw, dbt_staging, dbt_intermediate, dbt_analytics TO analyst_ro;

-- 3) west_coast_manager also needs read on the analytics marts (RLS still filters
--    raw.customers). Role + policy itself come from rls.sql.
GRANT USAGE  ON SCHEMA dbt_staging, dbt_intermediate, dbt_analytics TO west_coast_manager;
GRANT SELECT ON ALL TABLES IN SCHEMA dbt_staging, dbt_intermediate, dbt_analytics TO west_coast_manager;
