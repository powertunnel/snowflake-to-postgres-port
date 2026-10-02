"""Configuration: loads .env, exposes DeepSeek + Postgres settings."""
import os
from pathlib import Path
from dotenv import load_dotenv

# repo .env lives two levels up from this file: <repo>/.env is actually at
# /home/sandbox/snow/.env in this environment; load both candidates.
_here = Path(__file__).resolve()
for candidate in ("/home/sandbox/snow/.env", str(_here.parents[3] / ".env")):
    if os.path.exists(candidate):
        load_dotenv(candidate)
        break

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

# Postgres: connect via local socket as the OS superuser, then SET ROLE to the
# chosen agent identity so least-privilege + RLS apply to generated SQL.
PG = {
    "host": os.environ.get("PGHOST", "/var/run/postgresql"),
    "port": int(os.environ.get("PGPORT", "5432")),
    "dbname": os.environ.get("PGDATABASE", "snowport"),
    "user": os.environ.get("PGUSER", "sandbox"),
    "password": os.environ.get("PGPASSWORD", ""),
}

# Agent identities (roles the agent SET ROLEs into):
#   analyst_ro         -> read-only, BYPASSRLS (admin: sees all rows)
#   west_coast_manager -> read-only, RLS-filtered to CA/OR/WA
DEFAULT_ROLE = os.environ.get("AGENT_ROLE", "analyst_ro")

SEMANTIC_MODEL_PATH = str(_here.parent.parent / "semantic_model.yaml")
STATEMENT_TIMEOUT_MS = 15000
MAX_ROWS = 200
