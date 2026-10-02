# Postgres AI Agent — a local stand-in for the Snowflake Cortex AI layer

This package reproduces the *behavior* of the Snowflake Cortex Agent / Analyst /
Search / managed-MCP layer on top of the ported PostgreSQL `snowport` database,
using **DeepSeek** as the LLM. It is a functional equivalent, not a port — the
Snowflake services are proprietary and have no Postgres counterpart.

## How it maps to Snowflake

| Snowflake | Here |
|---|---|
| Cortex Analyst (text-to-SQL over a Semantic View) | `query_business_data` — DeepSeek writes SQL from `semantic_model.yaml`, executed read-only |
| Cortex Search (reviews + tickets) | `search_customer_feedback` — Postgres full-text search (`tsvector` + GIN) |
| Cortex Agent / CoWork (routing "what" vs "why") | `aiagent/agent.py` — DeepSeek function-calling routes across the two tools |
| Managed MCP Server | `aiagent/mcp_server.py` — an MCP (stdio) server exposing both tools |
| Row Access Policy *through* AI | every query runs under a DB role (`--role`), so RLS applies to generated SQL |
| Semantic View | `semantic_model.yaml` (hand-written) |

| Agent Evaluation (ground truth + LLM judge) | `aiagent/evaluate.py` + `eval_dataset.yaml` — answer_correctness + logical_consistency |

### Not included (and why)
- **Vector / semantic search**: `pgvector` isn't available here and DeepSeek has no
  embeddings endpoint, so search is keyword-based full-text. Upgrade path: install
  `pgvector`, add an `embedding vector(n)` column, generate embeddings with a local
  `sentence-transformers` model, and make `search_customer_feedback` hybrid.
- **Agent observability**: token/trace telemetry is not persisted (the eval harness
  captures per-question traces in its JSON output instead).

## Setup

```bash
# 1. deps (reuse the dbt venv or make a new one)
/home/sandbox/snow/.dbt-venv/bin/pip install -r requirements.txt

# 2. DB objects (FTS indexes + agent roles). Assumes schema.sql + rls.sql already ran.
psql -d snowport -f setup_agent_db.sql

# 3. DeepSeek key — already read from /home/sandbox/snow/.env (DEEPSEEK_API_KEY)
```

## Use

```bash
cd postgres-ai-agent
PY=/home/sandbox/snow/.dbt-venv/bin/python

# one-shot question (admin identity: all data)
$PY -m aiagent.agent "Show me the monthly revenue trend in 2025"

# the same question under row-level security -> only CA/OR/WA
$PY -m aiagent.agent "Total revenue and customer count by state" --role west_coast_manager

# interactive REPL
$PY -m aiagent.agent --role analyst_ro

# full trace (tool calls + SQL + rows)
$PY -m aiagent.agent "Why are customers returning ski boots?" --json
```

### As an MCP server (for Claude Code / Desktop / CoCo)

```bash
# run directly
/home/sandbox/snow/.dbt-venv/bin/python -m aiagent.mcp_server

# register with Claude Code
claude mcp add snowport-analytics -- \
  /home/sandbox/snow/.dbt-venv/bin/python -m aiagent.mcp_server
```

The connecting client's model then orchestrates across `query_business_data` and
`search_customer_feedback` — the role the Cortex Agent plays in Snowflake.

### Agent evaluation

Mirrors Snowflake Agent Evaluation: a ground-truth dataset (`eval_dataset.yaml`, the
lab's 7 questions localized to this data) scored by DeepSeek as judge on two 0–1
metrics — **answer_correctness** (vs. the ground-truth expectation) and
**logical_consistency** (reference-free: are tool choices, intermediate results, and
the final answer internally coherent and grounded?).

```bash
$PY -m aiagent.evaluate                      # all 7, writes eval_results.json
$PY -m aiagent.evaluate --only q4_ski_boot_returns
$PY -m aiagent.evaluate --role west_coast_manager
```

Prints a per-question table (routing / correctness / logic / pass) + averages;
`eval_results.json` has the full trace and judge rationales per question. The
consistency judge is fed the actual rows/search-hits the agent saw, so it flags real
ungrounded claims (e.g. invented quotes) rather than penalizing valid citations.

## Safety
- The SQL tool only runs a single `SELECT`/`WITH`; a keyword denylist + a
  `READ ONLY` transaction + `statement_timeout` are enforced in `db.py`.
- Queries execute under `analyst_ro` (read-only, all rows) or `west_coast_manager`
  (read-only, RLS-filtered). Never the table owner.

## Layout
```
semantic_model.yaml     semantic layer fed to text-to-SQL
setup_agent_db.sql      FTS indexes + agent roles (idempotent)
aiagent/config.py       .env + DB/LLM settings
aiagent/db.py           read-only execution + full-text search
aiagent/llm.py          DeepSeek chat wrapper
aiagent/tools.py        the two tools + tool schemas
aiagent/agent.py        orchestrator + CLI/REPL
aiagent/mcp_server.py   MCP stdio server
aiagent/evaluate.py     evaluation harness (LLM-as-judge)
eval_dataset.yaml       7 ground-truth eval questions
```
