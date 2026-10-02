"""Embedding provider for semantic search (fastembed / BAAI bge-small-en-v1.5).

DeepSeek has no embeddings endpoint, so semantic vectors come from a local ONNX
model (no PyTorch). 384-dim, cosine distance. The model is lazy-loaded once.
"""
from functools import lru_cache

MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBED_DIM = 384


@lru_cache(maxsize=1)
def _model():
    from fastembed import TextEmbedding
    return TextEmbedding(model_name=MODEL_NAME)


def embed_many(texts):
    """List[str] -> List[List[float]] (plain python floats for psycopg)."""
    return [[float(x) for x in v] for v in _model().embed(list(texts))]


def embed_one(text):
    return embed_many([text])[0]


def to_pgvector(vec) -> str:
    """Render a vector as the pgvector text literal '[1,2,3]'."""
    return "[" + ",".join(f"{float(x):.6f}" for x in vec) + "]"
