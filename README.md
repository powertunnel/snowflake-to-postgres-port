# Snowflake → PostgreSQL port

A working PostgreSQL port of the data, analytics, security, and AI layers from the
Snowflake quickstart
[**Build an End-to-End AI App on Snowflake**](https://github.com/Snowflake-Labs/sfguide-build-end-to-end-ai-app-on-snowflake)
(the retail snow-sports analytics lab).

The data-engineering, dbt, and row-level-security pieces **port** to Postgres. The
Snowflake-native AI services (Cortex Analyst / Search / Agent / CoWork, the managed
MCP server) have no Postgres equivalent, so they are **reconstructed** on an open
stack: PostgreSQL + full-text search + `pgvector` + an external LLM (DeepSeek) + a
custom agent and MCP server.

> Not ported (no Postgres equivalent): Dynamic Tables, Snowpipe Streaming, Gen2/Optima
> indexing, Iceberg, native Cortex SQL functions.

## What's here

| Path | What it is | Snowflake analog |
|---|---|---|
| `db/schema.sql` | `raw` schema DDL (6 tables) | `setup.sql` RAW tables |
| `db/gen_csv.py` | small-scale sample-data generator (CSV) | the lab's in-DB `GENERATOR` seed |
| `db/compat.sql` | `datediff`/`dayname`/`hour` shims | Snowflake built-ins |
| `db/rls.sql` | `west_coast_manager` role + Row-Level Security | Row Access Policy |
| `dbt-postgres/` | the ported dbt project (dbt-postgres) | `dbt-analytics/` (dbt-snowflake) |
| `postgres-ai-agent/` | DeepSeek agent + MCP server + eval harness | Cortex Agent / Analyst / Search / MCP / Agent Eval |

## Setup order

Assumes PostgreSQL 16 with a database `snowport` owned by a superuser you connect as.

```bash
# 1. schema + sample data (needs the upstream lab's seed_data_generator/)
psql -d snowport -f db/schema.sql
SEED_DIR=/path/to/sfguide.../seed_data_generator python db/gen_csv.py   # -> db/data/*.csv
psql -d snowport -c "\copy raw.customers       FROM 'db/data/customers.csv'       WITH (FORMAT csv, HEADER true)"
#   ...repeat \copy for orders, order_items, product_reviews, support_tickets
#   (product_catalog is 10 fixed rows — see db/schema.sql notes)

# 2. compatibility functions + row-level security
psql -d snowport -f db/compat.sql
psql -d snowport -f db/rls.sql

# 3. dbt
python -m venv .venv && . .venv/bin/activate
pip install dbt-postgres
cd dbt-postgres && dbt build --profiles-dir .      # PASS=72

# 4. AI agent (see postgres-ai-agent/README.md for detail)
pip install -r postgres-ai-agent/requirements.txt
psql -d snowport -f postgres-ai-agent/setup_agent_db.sql   # FTS + agent roles
#   optional semantic search: install pgvector, then: python -m aiagent.build_embeddings
#   set DEEPSEEK_API_KEY in a .env (see postgres-ai-agent/README.md)
cd postgres-ai-agent && python -m aiagent.agent "Total revenue by state"
```

## Notes

- Sample data is generated at a small scale (~50k orders) by default — edit the
  `config.*` overrides at the top of `db/gen_csv.py` to change it.
- `db/gen_csv.py` imports the upstream lab's `seed_data_generator/` (Apache-2.0);
  it is not vendored here. Point `SEED_DIR` at it.
- Semantic search uses `fastembed` (`BAAI/bge-small-en-v1.5`, 384-dim) because
  DeepSeek has no embeddings endpoint; search falls back to keyword FTS if `pgvector`
  isn't installed.

## Credit

Built on the Snowflake-Labs quickstart linked above (Apache-2.0). This port is an
independent adaptation, not affiliated with or endorsed by Snowflake.
