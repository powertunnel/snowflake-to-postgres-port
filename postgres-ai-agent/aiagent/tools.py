"""The two agent tools: query_business_data (text-to-SQL) and
search_customer_feedback (full-text search). These mirror the Snowflake
Cortex Analyst and Cortex Search tools."""
import json
from pathlib import Path
from . import db, llm, config

_SEMANTIC = Path(config.SEMANTIC_MODEL_PATH).read_text()

_SQL_SYSTEM = f"""You are a PostgreSQL text-to-SQL generator for a retail analytics DB.
Translate the user's question into ONE read-only PostgreSQL SELECT query.

Rules:
- Output ONLY JSON: {{"sql": "<query>", "explanation": "<one line>"}}
- Single SELECT (or WITH ... SELECT). No DML/DDL, no semicolons, no comments.
- Use ONLY the tables/columns in the semantic model below, schema-qualified.
- PostgreSQL dialect: date_trunc('month', ts), to_char(...), etc.
- Limit result rows to {config.MAX_ROWS} unless the question implies an aggregate.

SEMANTIC MODEL:
{_SEMANTIC}
"""


def query_business_data(question: str, role: str = None) -> dict:
    """Text-to-SQL: generate SQL from the question, run it read-only, return rows."""
    msg = llm.chat(
        [{"role": "system", "content": _SQL_SYSTEM},
         {"role": "user", "content": question}],
        temperature=0.0, max_tokens=700,
    )
    spec = llm.extract_json(msg["content"])
    sql = spec["sql"]
    try:
        cols, rows = db.run_select(sql, role=role)
        return {"sql": sql, "explanation": spec.get("explanation", ""),
                "columns": cols, "rows": rows, "row_count": len(rows)}
    except Exception as e:
        return {"sql": sql, "error": str(e)}


def count_feedback_mentions(terms: str, source: str = "reviews",
                            group_by: str = "none", role: str = None) -> dict:
    """Accurate counts/breakdowns of feedback mentioning `terms` (scans all rows)."""
    return db.count_feedback_mentions(terms, source=source, group_by=group_by, role=role)


def search_customer_feedback(query: str, source: str = "all",
                             filters: dict = None, role: str = None) -> dict:
    """Full-text search over reviews + support tickets."""
    results = db.search_feedback(query, source=source, filters=filters or {}, role=role)
    # Trim bodies for compactness in the LLM context.
    for r in results:
        if r.get("body") and len(r["body"]) > 300:
            r["body"] = r["body"][:300] + "…"
        r.pop("rank", None)
    return {"query": query, "source": source, "filters": filters or {},
            "result_count": len(results), "results": results}


# OpenAI/DeepSeek-style tool schemas for the orchestrator's function-calling.
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "query_business_data",
            "description": ("Answer quantitative/structured questions about orders, "
                            "revenue, customers, products via text-to-SQL over the "
                            "Postgres warehouse. Use for 'how many', 'trend', 'by state', "
                            "'top products', 'lifetime value', etc."),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string",
                                 "description": "The analytical question to answer with SQL."}
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "count_feedback_mentions",
            "description": ("Return ACCURATE counts (and optional breakdowns) of reviews/"
                            "tickets whose text mentions given terms. Use for 'how many "
                            "mention X', 'which products are most affected', 'count by "
                            "category'. Unlike search, this scans ALL matching rows, so "
                            "prefer it over counting search results."),
            "parameters": {
                "type": "object",
                "properties": {
                    "terms": {"type": "string",
                              "description": "Space-separated terms, OR'd (e.g. 'size sizing fit')."},
                    "source": {"type": "string", "enum": ["reviews", "tickets", "all"]},
                    "group_by": {"type": "string",
                                 "enum": ["none", "product", "rating", "category", "priority", "status"],
                                 "description": ("reviews support none|product|rating; "
                                                 "tickets support none|category|priority|status.")},
                },
                "required": ["terms"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_customer_feedback",
            "description": ("Search unstructured product reviews and support tickets for "
                            "themes/complaints. Use for 'why', 'what do customers say', "
                            "'reviews mentioning X', 'complaint themes', returns, sizing, etc."),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search terms."},
                    "source": {"type": "string", "enum": ["reviews", "tickets", "all"],
                               "description": "Which corpus to search."},
                    "filters": {
                        "type": "object",
                        "description": (
                            "Optional filters. For ratings, map the wording precisely: "
                            "'below N' / 'under N' / 'less than N' -> {\"rating_lt\": N} (strict); "
                            "'N or below' / 'at most N' / '<= N' -> {\"rating_lte\": N}; "
                            "'at least N' -> {\"min_rating\": N}. "
                            "Also: product_id (int), category (str), priority (str)."),
                    },
                },
                "required": ["query"],
            },
        },
    },
]

DISPATCH = {
    "query_business_data": lambda args, role: query_business_data(args["question"], role=role),
    "count_feedback_mentions": lambda args, role: count_feedback_mentions(
        args["terms"], args.get("source", "reviews"), args.get("group_by", "none"), role=role),
    "search_customer_feedback": lambda args, role: search_customer_feedback(
        args["query"], args.get("source", "all"), args.get("filters"), role=role),
}
