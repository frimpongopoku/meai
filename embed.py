"""Generate embeddings for content that doesn't have them yet."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from chunking import chunk_action, chunk_event, chunk_testimonial
from db import db_session
from embedding_client import EMBEDDING_MODEL, embed_texts
from models import Action, Embedding, Event, Testimonial

# Batch size for Voyage API calls. Voyage handles up to 128 inputs per request
# for voyage-3-large; we use 32 to keep latency low and errors recoverable.
BATCH_SIZE = 32


def _records_needing_embeddings(
    session: Session, model_class, content_type: str, site_id: int
):
    """Find records of this type that don't yet have embeddings.

    A record needs embeddings if no rows exist in the embeddings table
    referencing its content_id. (Cascade-delete in ingestion ensures this
    flag stays accurate even after content changes.)
    """
    # Subquery: content_ids that already have at least one embedding
    embedded_ids_subq = (
        select(Embedding.content_id)
        .where(Embedding.content_type == content_type)
        .distinct()
    )

    return (
        session.execute(
            select(model_class).where(
                model_class.site_id == site_id,
                model_class.archived_at.is_(None),
                model_class.id.notin_(embedded_ids_subq),
            )
        )
        .scalars()
        .all()
    )


def _persist_chunks(
    session: Session,
    content_type: str,
    content_id: str,
    site_id: int,
    chunks: list[tuple[int, str]],
    embeddings: list[list[float]],
):
    """Save chunks and their embeddings as rows in the embeddings table."""
    for (chunk_index, chunk_text), embedding in zip(chunks, embeddings):
        session.add(
            Embedding(
                content_type=content_type,
                content_id=content_id,
                site_id=site_id,
                chunk_index=chunk_index,
                chunk_text=chunk_text,
                embedding=embedding,
                embedding_model=EMBEDDING_MODEL,
            )
        )


def embed_actions(site_id: int) -> dict:
    """Generate embeddings for actions on a site that don't have them yet."""
    stats = {"actions_embedded": 0, "chunks_created": 0}

    with db_session() as session:
        pending = _records_needing_embeddings(session, Action, "action", site_id)

        if not pending:
            return stats

        # Build (action, chunks) pairs for all pending actions
        action_chunks: list[tuple[Action, list[tuple[int, str]]]] = []
        for action in pending:
            chunks = chunk_action(action)
            action_chunks.append((action, chunks))

        # Flatten chunk texts for batched embedding API calls
        all_texts: list[str] = []
        for _, chunks in action_chunks:
            for _, text in chunks:
                all_texts.append(text)

        # Embed in batches
        all_embeddings: list[list[float]] = []
        for i in range(0, len(all_texts), BATCH_SIZE):
            batch = all_texts[i : i + BATCH_SIZE]
            all_embeddings.extend(embed_texts(batch, input_type="document"))

        # Persist back to DB, walking embeddings in order
        embedding_cursor = 0
        for action, chunks in action_chunks:
            chunk_embeddings = all_embeddings[
                embedding_cursor : embedding_cursor + len(chunks)
            ]
            _persist_chunks(
                session, "action", action.id, site_id, chunks, chunk_embeddings
            )
            embedding_cursor += len(chunks)
            stats["actions_embedded"] += 1
            stats["chunks_created"] += len(chunks)

    return stats


def embed_testimonials(site_id: int) -> dict:
    """Generate embeddings for testimonials on a site that don't have them yet.

    Each testimonial's embedded text includes the related action's title
    as context. When an action's title changes, ingest cascade-deletes
    these embeddings so they regenerate here on the next embed run.
    """
    stats = {"testimonials_embedded": 0, "chunks_created": 0}

    with db_session() as session:
        pending = _records_needing_embeddings(
            session, Testimonial, "testimonial", site_id
        )

        if not pending:
            return stats

        # Resolve related action titles in bulk for the testimonials we need
        action_ids_to_lookup = {
            t.related_action_id for t in pending if t.related_action_id
        }
        action_titles: dict[str, str] = {}
        if action_ids_to_lookup:
            rows = session.execute(
                select(Action.id, Action.title).where(
                    Action.id.in_(action_ids_to_lookup)
                )
            ).all()
            action_titles = {str(row.id): row.title for row in rows}

        testimonial_chunks: list[tuple[Testimonial, list[tuple[int, str]]]] = []
        for testimonial in pending:
            related_title = (
                action_titles.get(str(testimonial.related_action_id))
                if testimonial.related_action_id
                else None
            )
            chunks = chunk_testimonial(testimonial, related_title)
            testimonial_chunks.append((testimonial, chunks))

        all_texts = [text for _, chunks in testimonial_chunks for _, text in chunks]

        all_embeddings: list[list[float]] = []
        for i in range(0, len(all_texts), BATCH_SIZE):
            batch = all_texts[i : i + BATCH_SIZE]
            all_embeddings.extend(embed_texts(batch, input_type="document"))

        embedding_cursor = 0
        for testimonial, chunks in testimonial_chunks:
            chunk_embeddings = all_embeddings[
                embedding_cursor : embedding_cursor + len(chunks)
            ]
            _persist_chunks(
                session,
                "testimonial",
                testimonial.id,
                site_id,
                chunks,
                chunk_embeddings,
            )
            embedding_cursor += len(chunks)
            stats["testimonials_embedded"] += 1
            stats["chunks_created"] += len(chunks)

    return stats


def embed_events(site_id: int) -> dict:
    """Generate embeddings for events on a site that don't have them yet."""
    stats = {"events_embedded": 0, "chunks_created": 0}

    with db_session() as session:
        pending = _records_needing_embeddings(session, Event, "event", site_id)

        if not pending:
            return stats

        event_chunks: list[tuple[Event, list[tuple[int, str]]]] = []
        for event in pending:
            chunks = chunk_event(event)
            event_chunks.append((event, chunks))

        all_texts = [text for _, chunks in event_chunks for _, text in chunks]

        all_embeddings: list[list[float]] = []
        for i in range(0, len(all_texts), BATCH_SIZE):
            batch = all_texts[i : i + BATCH_SIZE]
            all_embeddings.extend(embed_texts(batch, input_type="document"))

        embedding_cursor = 0
        for event, chunks in event_chunks:
            chunk_embeddings = all_embeddings[
                embedding_cursor : embedding_cursor + len(chunks)
            ]
            _persist_chunks(
                session, "event", event.id, site_id, chunks, chunk_embeddings
            )
            embedding_cursor += len(chunks)
            stats["events_embedded"] += 1
            stats["chunks_created"] += len(chunks)

    return stats
