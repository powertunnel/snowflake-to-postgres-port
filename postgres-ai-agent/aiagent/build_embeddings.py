"""One-time backfill: add vector columns to the feedback tables, embed every row,
and build HNSW cosine indexes. Requires the pgvector extension.

Run (as the DB owner/superuser):
  python -m aiagent.build_embeddings
"""
import sys
import psycopg2
import psycopg2.extras
from . import config, embeddings as E

TABLES = {
    "raw.product_reviews": ("review_id",
                            "coalesce(review_title,'') || ' ' || coalesce(review_text,'')"),
    "raw.support_tickets": ("ticket_id",
                            "coalesce(subject,'') || ' ' || coalesce(description,'') || ' ' || coalesce(resolution,'')"),
}
BATCH = 500


def ensure_extension_and_columns(cur):
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
    for tbl in TABLES:
        cur.execute(f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS embedding vector({E.EMBED_DIM})")


def backfill(conn, tbl, pk, text_expr):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(f"SELECT {pk} AS id, {text_expr} AS txt FROM {tbl} WHERE embedding IS NULL")
        rows = cur.fetchall()
    print(f"  {tbl}: {len(rows)} rows to embed")
    done = 0
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i + BATCH]
        vecs = E.embed_many([r["txt"] for r in chunk])
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                f"UPDATE {tbl} AS t SET embedding = v.emb::vector "
                f"FROM (VALUES %s) AS v(id, emb) WHERE t.{pk} = v.id",
                [(r["id"], E.to_pgvector(vec)) for r, vec in zip(chunk, vecs)],
            )
        conn.commit()
        done += len(chunk)
        print(f"    embedded {done}/{len(rows)}", file=sys.stderr)


def build_index(cur, tbl):
    idx = f"idx_{tbl.split('.')[-1]}_embedding"
    cur.execute(f"CREATE INDEX IF NOT EXISTS {idx} ON {tbl} "
                f"USING hnsw (embedding vector_cosine_ops)")


def main():
    conn = psycopg2.connect(**config.PG)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            ensure_extension_and_columns(cur)
        conn.commit()
        for tbl, (pk, text_expr) in TABLES.items():
            backfill(conn, tbl, pk, text_expr)
        with conn.cursor() as cur:
            for tbl in TABLES:
                build_index(cur, tbl)
        conn.commit()
        # grant read on the new column implicitly covered by table SELECT grants.
        print("Done: embeddings backfilled and HNSW indexes built.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
