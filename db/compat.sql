-- Snowflake->PostgreSQL compatibility shims for the ported dbt models.
-- Lets the models keep their original Snowflake function calls (datediff / dayname
-- / hour) unchanged. Installed in public (on the default search_path).
-- NOTE: current_date() -> current_date was edited directly in the models, because
-- current_date is a reserved keyword in Postgres and cannot be a user function.

-- DATEDIFF(part, start, end) -> integer, Snowflake signed semantics.
-- Params are timestamptz so date / timestamp / timestamptz args all cast implicitly
-- (a single signature avoids overload ambiguity). Only the parts the models use
-- ('day','month','year') are implemented; anything else raises.
CREATE OR REPLACE FUNCTION public.datediff(part text, s timestamptz, e timestamptz)
RETURNS integer
LANGUAGE plpgsql IMMUTABLE AS $$
BEGIN
    IF lower(part) NOT IN ('day','month','year') THEN
        RAISE EXCEPTION 'datediff: unsupported part %', part;
    END IF;
    RETURN CASE lower(part)
        WHEN 'day'   THEN (e::date - s::date)
        WHEN 'month' THEN (EXTRACT(YEAR FROM e)::int - EXTRACT(YEAR FROM s)::int) * 12
                          + (EXTRACT(MONTH FROM e)::int - EXTRACT(MONTH FROM s)::int)
        WHEN 'year'  THEN (EXTRACT(YEAR FROM e)::int - EXTRACT(YEAR FROM s)::int)
    END;
END;
$$;

-- DAYNAME(ts) -> 'Mon','Tue',...  (Snowflake's 3-letter abbreviation)
CREATE OR REPLACE FUNCTION public.dayname(ts timestamp)
RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT trim(to_char(ts, 'Dy'));
$$;

-- HOUR(ts) -> integer hour of day
CREATE OR REPLACE FUNCTION public.hour(ts timestamp)
RETURNS integer
LANGUAGE sql IMMUTABLE AS $$
    SELECT EXTRACT(HOUR FROM ts)::int;
$$;
