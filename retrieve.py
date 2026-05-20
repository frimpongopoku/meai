"""Semantic retrieval over embedded content.

The bridge between vector search and structured records. Functions here
return clean structured data (Action/Testimonial/Event records), not raw
chunks — chunks are an internal detail of how we make retrieval fast.
"""

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from db import db_session
from embedding_client import embed_texts
from models import Action, Embedding, Event, Testimonial


ContentType = Literal["action", "testimonial", "event"]


@dataclass
class SearchHit:
    """A single result from semantic search.

    Holds the matched record plus the best chunk that matched (for
    debugging and showing 'why this matched') and the distance score.
    """
    content_type: ContentType
    content_id: str
    distance: float
    matched_chunk_text: str
    record: Action | Testimonial | Event


def _search_content_type(
    session: Session,
    site_id: int,
    content_type: ContentType,
    query_vec: list[float],
    k: int,
) -> list[SearchHit]:
    """Run semantic search for one content type, returning the top K records.

    Multi-chunk records (like actions) may match on multiple chunks. We
    collapse by content_id, keeping the best-matching chunk per record.
    """
    # Step 1: get more chunks than k, because multiple chunks can belong
    # to the same record. Asking for 3x gives headroom to collapse and
    # still have k unique records.
    candidates = session.execute(
        select(
            Embedding.content_id,
            Embedding.chunk_text,
            Embedding.embedding.cosine_distance(query_vec).label("distance"),
        )
        .where(
            Embedding.site_id == site_id,
            Embedding.content_type == content_type,
        )
        .order_by("distance")
        .limit(k * 3)
    ).all()

    # Step 2: collapse to one entry per content_id, keeping the best chunk
    best_per_record: dict[str, tuple[float, str]] = {}
    for row in candidates:
        content_id = str(row.content_id)
        if content_id not in best_per_record:
            best_per_record[content_id] = (row.distance, row.chunk_text)

    # Step 3: take top k records by distance
    top_records = sorted(best_per_record.items(), key=lambda x: x[1][0])[:k]
    if not top_records:
        return []

    # Step 4: fetch the structured records, filtered to non-archived only
    content_ids = [cid for cid, _ in top_records]
    model_class = {
        "action": Action,
        "testimonial": Testimonial,
        "event": Event,
    }[content_type]

    records = session.execute(
        select(model_class).where(
            model_class.id.in_(content_ids),
            model_class.archived_at.is_(None),
        )
    ).scalars().all()
    records_by_id = {str(r.id): r for r in records}

    # Step 5: build hits in the order of best match, skipping any that
    # were archived between the embedding query and the records query
    hits: list[SearchHit] = []
    for cid, (distance, chunk_text) in top_records:
        record = records_by_id.get(cid)
        if record is None:
            continue
        hits.append(SearchHit(
            content_type=content_type,
            content_id=cid,
            distance=distance,
            matched_chunk_text=chunk_text,
            record=record,
        ))

    return hits


def search(
    site_id: int,
    query: str,
    k: int = 5,
    content_types: list[ContentType] | None = None,
) -> dict[ContentType, list[SearchHit]]:
    """Semantic search across content types for a single site.

    Returns a dict keyed by content_type. Each value is a list of SearchHit
    objects, ordered by best match first.
    """
    if content_types is None:
        content_types = ["action", "testimonial", "event"]

    # Embed the query with input_type="query" — Voyage uses this hint to
    # generate embeddings optimized for the query-side of the search.
    query_vec = embed_texts([query], input_type="query")[0]

    with db_session() as session:
        return {
            ct: _search_content_type(session, site_id, ct, query_vec, k)
            for ct in content_types
        }