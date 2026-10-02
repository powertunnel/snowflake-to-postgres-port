"""Postgres access: read-only execution under a chosen role (RLS + least priv)."""
import re
import psycopg2
import psycopg2.extras
from . import config

# Only single read-only SELECT/WITH statements are allowed from the SQL tool.
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|truncate|alter|create|grant|revoke|copy|"
    r"merge|call|do|vacuum|reindex|comment|set\s+role|reset)\b",
    re.IGNORECASE,
)


class SqlNotAllowed(Exception):
    pass


def _or_tsquery(text: str) -> str:
    """Turn free text into an OR tsquery string (e.g. 'ski boots return' ->
    'ski | boots | return') so multi-word searches recall docs matching ANY term,
    ranked by how many match. Avoids websearch_to_tsquery's all-AND behavior that
    returns 0 hits for natural-language phrases. Returned string is fed to
    to_tsquery('english', ...), which also stems each term."""
    tokens = re.findall(r"[A-Za-z0-9]+", (text or "").lower())
    stop = {"the", "a", "an", "of", "for", "to", "and", "or", "in", "on", "is",
            "are", "what", "why", "do", "does", "with", "about", "my"}
    tokens = [t for t in tokens if t not in stop and len(t) > 1]
    return " | ".join(dict.fromkeys(tokens))  # dedupe, preserve order


def validate_select(sql: str) -> str:
    s = sql.strip().rstrip(";").strip()
    if ";" in s:
        raise SqlNotAllowed("Only a single statement is allowed.")
    if not re.match(r"^\s*(select|with)\b", s, re.IGNORECASE):
        raise SqlNotAllowed("Only SELECT/WITH queries are allowed.")
    if _FORBIDDEN.search(s):
        raise SqlNotAllowed("Query contains a forbidden keyword.")
    return s


def run_select(sql: str, role: str = None, max_rows: int = None):
    """Execute a validated read-only SELECT as `role`. Returns (columns, rows)."""
    role = role or config.DEFAULT_ROLE
    max_rows = max_rows or config.MAX_ROWS
    safe_sql = validate_select(sql)

    conn = psycopg2.connect(**config.PG)
    try:
        conn.set_session(readonly=True, autocommit=False)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # SET ROLE must run before READ ONLY transaction work; do it in its own tx.
            cur.execute(f"SET ROLE {psycopg2.extensions.quote_ident(role, conn)}")
            cur.execute(f"SET statement_timeout = {int(config.STATEMENT_TIMEOUT_MS)}")
            cur.execute(safe_sql)
            rows = cur.fetchmany(max_rows)
            cols = [d[0] for d in cur.description] if cur.description else []
        conn.rollback()
        return cols, [dict(r) for r in rows]
    finally:
        conn.close()


# Per-source filter clauses (shared by keyword + vector branches).
def _review_filter_sql(filters):
    clauses, params = [], {}
    if "rating_lt" in filters:
        clauses.append("rating < %(rating_lt)s"); params["rating_lt"] = filters["rating_lt"]
    if "rating_lte" in filters:
        clauses.append("rating <= %(rating_lte)s"); params["rating_lte"] = filters["rating_lte"]
    if "max_rating" in filters:
        clauses.append("rating <= %(max_rating)s"); params["max_rating"] = filters["max_rating"]
    if "min_rating" in filters:
        clauses.append("rating >= %(min_rating)s"); params["min_rating"] = filters["min_rating"]
    if "product_id" in filters:
        clauses.append("product_id = %(product_id)s"); params["product_id"] = filters["product_id"]
    return clauses, params


def _ticket_filter_sql(filters):
    clauses, params = [], {}
    if "category" in filters:
        clauses.append("category = %(category)s"); params["category"] = filters["category"]
    if "priority" in filters:
        clauses.append("priority = %(priority)s"); params["priority"] = filters["priority"]
    return clauses, params


_SRC_SPEC = {
    "reviews": {
        "table": "raw.product_reviews", "pk": "review_id",
        "select": "'review' AS kind, review_id AS pk, product_id, rating, "
                  "review_title AS title, review_text AS body",
        "filters": _review_filter_sql,
    },
    "tickets": {
        "table": "raw.support_tickets", "pk": "ticket_id",
        "select": "'ticket' AS kind, ticket_id AS pk, category, priority, status, "
                  "subject AS title, description AS body",
        "filters": _ticket_filter_sql,
    },
}

_HAS_EMB = None


def _has_embeddings(cur) -> bool:
    global _HAS_EMB
    if _HAS_EMB is None:
        cur.execute("""
            SELECT COUNT(*) AS n FROM information_schema.columns
            WHERE table_schema='raw' AND table_name IN ('product_reviews','support_tickets')
              AND column_name='embedding'
        """)
        row = cur.fetchone()
        _HAS_EMB = (row["n"] if isinstance(row, dict) else row[0]) >= 2
    return _HAS_EMB


def _fts_rank(cur, src, tsq, filters, k):
    spec = _SRC_SPEC[src]
    clauses, params = spec["filters"](filters)
    where = ["search_tsv @@ to_tsquery('english', %(q)s)"] + clauses
    params["q"] = tsq
    cur.execute(f"SELECT {spec['select']} FROM {spec['table']} "
                f"WHERE {' AND '.join(where)} "
                f"ORDER BY ts_rank(search_tsv, to_tsquery('english', %(q)s)) DESC "
                f"LIMIT %(k)s", {**params, "k": k})
    return [dict(r) for r in cur.fetchall()]


def _vector_rank(cur, src, qvec_literal, filters, k):
    spec = _SRC_SPEC[src]
    clauses, params = spec["filters"](filters)
    where = ["embedding IS NOT NULL"] + clauses
    params["qv"] = qvec_literal
    cur.execute(f"SELECT {spec['select']} FROM {spec['table']} "
                f"WHERE {' AND '.join(where)} "
                f"ORDER BY embedding <=> %(qv)s::vector "
                f"LIMIT %(k)s", {**params, "k": k})
    return [dict(r) for r in cur.fetchall()]


def _rrf(ranked_lists, limit, k_const=60):
    """Reciprocal Rank Fusion of several ranked lists into one, by (kind,pk)."""
    scores, items = {}, {}
    for lst in ranked_lists:
        for rank, row in enumerate(lst):
            key = (row["kind"], row["pk"])
            scores[key] = scores.get(key, 0.0) + 1.0 / (k_const + rank + 1)
            items[key] = row
    fused = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    out = []
    for key, score in fused[:limit]:
        row = dict(items[key]); row.pop("pk", None); row["rank"] = round(score, 5)
        out.append(row)
    return out


def search_feedback(query: str, source: str = "all", filters: dict = None,
                    role: str = None, limit: int = 10, mode: str = "auto"):
    """Search product_reviews/support_tickets.

    mode: 'keyword' (full-text), 'semantic' (vector), 'hybrid' (RRF of both),
          or 'auto' -> hybrid when embeddings exist, else keyword.
    source: 'reviews' | 'tickets' | 'all'. filters: rating_lt/lte/min/max,
            product_id, category, priority.
    """
    role = role or config.DEFAULT_ROLE
    filters = filters or {}
    tsq = _or_tsquery(query)
    srcs = ["reviews", "tickets"] if source == "all" else [source]
    pool = max(limit, 20)

    conn = psycopg2.connect(**config.PG)
    try:
        conn.set_session(readonly=True, autocommit=False)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"SET ROLE {psycopg2.extensions.quote_ident(role, conn)}")
            cur.execute(f"SET statement_timeout = {int(config.STATEMENT_TIMEOUT_MS)}")

            use_mode = mode
            if mode == "auto":
                use_mode = "hybrid" if _has_embeddings(cur) else "keyword"
            if use_mode in ("semantic", "hybrid") and not _has_embeddings(cur):
                use_mode = "keyword"  # pgvector not set up yet

            qvec = None
            if use_mode in ("semantic", "hybrid"):
                from . import embeddings as E
                qvec = E.to_pgvector(E.embed_one(query))

            ranked_lists = []
            for src in srcs:
                if use_mode in ("keyword", "hybrid") and tsq:
                    ranked_lists.append(_fts_rank(cur, src, tsq, filters, pool))
                if use_mode in ("semantic", "hybrid") and qvec is not None:
                    ranked_lists.append(_vector_rank(cur, src, qvec, filters, pool))
        conn.rollback()
        return _rrf(ranked_lists, limit)
    finally:
        conn.close()


# group_by -> (schema-qualified table, grouping SQL expr, label). Allowlisted to
# keep the dynamic column out of untrusted input.
_COUNT_GROUPINGS = {
    "reviews": {
        "none":     ("raw.product_reviews", None, None),
        "product":  ("raw.product_reviews JOIN raw.product_catalog p USING (product_id)",
                     "p.product_name", "product_name"),
        "rating":   ("raw.product_reviews", "rating::text", "rating"),
    },
    "tickets": {
        "none":     ("raw.support_tickets", None, None),
        "category": ("raw.support_tickets", "category", "category"),
        "priority": ("raw.support_tickets", "priority", "priority"),
        "status":   ("raw.support_tickets", "status", "status"),
    },
}


def count_feedback_mentions(terms, source="reviews", group_by="none", role=None):
    """Accurate COUNT/GROUP BY of feedback rows whose text matches `terms` (OR'd).
    Scans ALL matching rows (unlike the capped search tool). Returns per-source
    totals and an optional breakdown. `group_by` is allowlisted per source."""
    role = role or config.DEFAULT_ROLE
    if isinstance(terms, (list, tuple)):
        terms = " ".join(str(t) for t in terms)
    tsq = _or_tsquery(terms)
    if not tsq:
        return {"terms": terms, "error": "no searchable terms"}
    sources = ["reviews", "tickets"] if source == "all" else [source]

    conn = psycopg2.connect(**config.PG)
    try:
        conn.set_session(readonly=True, autocommit=False)
        out = {"terms": terms, "tsquery": tsq, "source": source,
               "group_by": group_by, "per_source": {}}
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"SET ROLE {psycopg2.extensions.quote_ident(role, conn)}")
            cur.execute(f"SET statement_timeout = {int(config.STATEMENT_TIMEOUT_MS)}")
            for src in sources:
                grp = group_by if group_by in _COUNT_GROUPINGS[src] else "none"
                frm, expr, label = _COUNT_GROUPINGS[src][grp]
                cur.execute(
                    f"SELECT COUNT(*) AS total FROM {frm} "
                    f"WHERE search_tsv @@ to_tsquery('english', %(q)s)", {"q": tsq})
                total = cur.fetchone()["total"]
                entry = {"total": total, "effective_group_by": grp}
                if expr:
                    cur.execute(
                        f"SELECT {expr} AS {label}, COUNT(*) AS mentions FROM {frm} "
                        f"WHERE search_tsv @@ to_tsquery('english', %(q)s) "
                        f"GROUP BY {expr} ORDER BY mentions DESC", {"q": tsq})
                    entry["breakdown"] = [dict(r) for r in cur.fetchall()]
                out["per_source"][src] = entry
        conn.rollback()
        out["total"] = sum(v["total"] for v in out["per_source"].values())
        return out
    finally:
        conn.close()
