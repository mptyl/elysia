"""Shared embedding model for client-side vector computation.

Used by ethical guardrails and other components that need to compute
query vectors for hybrid search against collections without a vectorizer module.
"""

from functools import lru_cache

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def get_embedding_model():
    """Load and cache the sentence-transformer embedding model."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL_NAME)


def embed_query(text: str) -> list[float]:
    """Encode a query string into a vector."""
    model = get_embedding_model()
    return model.encode(text).tolist()
