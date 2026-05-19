"""Wrapper around the Voyage AI embedding API."""

import os

# import voyageai
from voyageai.client import Client as VoyageClient
from typing import cast

# Model and dimension configuration.
# IMPORTANT: if changing the model, you must also update the schema's
# Vector(N) dimension and run a migration.
EMBEDDING_MODEL = "voyage-3-large"
EMBEDDING_DIM = 1024


_client: VoyageClient | None = None


def _get_client() -> VoyageClient:
    """Lazy-initialize the Voyage client."""
    global _client
    if _client is None:
        _client = VoyageClient(api_key=os.environ["VOYAGE_API_KEY"])
    return _client


def embed_texts(texts: list[str], input_type: str = "document") -> list[list[float]]:
    """Embed a batch of texts using Voyage.

    input_type: 'document' for content being indexed, 'query' for search queries.
    Voyage uses this to optimize embeddings differently for each role.

    Returns a list of embedding vectors in the same order as inputs.
    """
    if not texts:
        return []

    client = _get_client()
    result = client.embed(
        texts=texts,
        model=EMBEDDING_MODEL,
        input_type=input_type,
        output_dimension=EMBEDDING_DIM,
    )
    return cast(list[list[float]], result.embeddings)
