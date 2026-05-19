"""Ingestion: pull from WordPress, transform, upsert into pgvector."""

from datetime import datetime

from sqlalchemy import select, update

# from sqlalchemy.engine import CursorResult

from db import db_session
from hashing import compute_content_hash
from models import Action
from wp_repository import WPAction, get_actions
from models import Action, Testimonial
from wp_repository import WPAction, WPTestimonial, get_actions, get_testimonials
from models import Action, Event, Testimonial
from wp_repository import (
    WPAction,
    WPEvent,
    WPTestimonial,
    get_actions,
    get_events,
    get_testimonials,
)
from sqlalchemy import delete, select, update
from models import Action, Embedding, Event, Testimonial


def _action_hash(wp_action: WPAction) -> str:
    """Compute a content hash for an action based on its meaningful fields."""
    return compute_content_hash(
        wp_action.title,
        wp_action.description_text,
        wp_action.steps_to_take_text or "",
        wp_action.deep_dive_text or "",
        wp_action.is_featured,
        wp_action.display_order,
        sorted(wp_action.classifications),
        wp_action.url,
    )


def _testimonial_hash(wp_testimonial: WPTestimonial) -> str:
    """Compute a content hash for a testimonial based on its meaningful fields."""
    return compute_content_hash(
        wp_testimonial.title or "",
        wp_testimonial.body_text,
        wp_testimonial.submitted_by or "",
        wp_testimonial.display_name or "",
        wp_testimonial.related_action_wp_post_id,
        wp_testimonial.display_order,
    )


def _event_hash(wp_event: WPEvent) -> str:
    """Compute a content hash for an event based on its meaningful fields."""
    return compute_content_hash(
        wp_event.title,
        wp_event.description_text,
        wp_event.start_datetime_utc,
        wp_event.end_datetime_utc,
        wp_event.timezone or "",
        wp_event.venue_name or "",
        wp_event.venue_address or "",
        wp_event.organizer_names or "",
        wp_event.organizer_emails or "",
        wp_event.event_url or "",
        wp_event.cost or "",
    )


def _resolve_action_id(session, site_id: int, wp_post_id: int | None) -> str | None:
    """Look up the internal UUID for an action given its WP post ID."""
    if wp_post_id is None:
        return None
    result = session.execute(
        select(Action.id).where(
            Action.site_id == site_id,
            Action.wp_post_id == wp_post_id,
        )
    ).scalar_one_or_none()
    return result


def ingest_actions(site_id: int) -> dict:
    """Ingest all published actions for a site into pgvector.

    Returns a summary dict with counts: inserted, updated, unchanged, archived, unarchived.
    """
    wp_actions = get_actions(site_id)
    stats = {
        "inserted": 0,
        "updated": 0,
        "unchanged": 0,
        "archived": 0,
        "unarchived": 0,
        "total_in_wp": len(wp_actions),
    }

    seen_wp_post_ids = {wp.wp_post_id for wp in wp_actions}

    with db_session() as session:
        # Process each WP record (insert, update, or mark unchanged)
        for wp_action in wp_actions:
            new_hash = _action_hash(wp_action)

            existing = session.execute(
                select(Action).where(
                    Action.site_id == site_id,
                    Action.wp_post_id == wp_action.wp_post_id,
                )
            ).scalar_one_or_none()

            if existing is None:
                session.add(
                    Action(
                        site_id=site_id,
                        wp_post_id=wp_action.wp_post_id,
                        title=wp_action.title,
                        description_html=wp_action.description_html,
                        description_text=wp_action.description_text,
                        steps_to_take_html=wp_action.steps_to_take_html,
                        steps_to_take_text=wp_action.steps_to_take_text,
                        deep_dive_html=wp_action.deep_dive_html,
                        deep_dive_text=wp_action.deep_dive_text,
                        is_featured=wp_action.is_featured,
                        display_order=wp_action.display_order,
                        classifications=wp_action.classifications,
                        url=wp_action.url,
                        status=wp_action.status,
                        modified_at=wp_action.modified_at,
                        content_hash=new_hash,
                        ingested_at=datetime.utcnow(),
                    )
                )
                stats["inserted"] += 1
            else:
                # Unarchive if it was previously archived
                was_archived = existing.archived_at is not None
                title_changed = existing.title != wp_action.title
                if was_archived:
                    existing.archived_at = None
                    stats["unarchived"] += 1

                if existing.content_hash == new_hash and not was_archived:
                    stats["unchanged"] += 1
                else:
                    existing.title = wp_action.title
                    existing.description_html = wp_action.description_html
                    existing.description_text = wp_action.description_text
                    existing.steps_to_take_html = wp_action.steps_to_take_html
                    existing.steps_to_take_text = wp_action.steps_to_take_text
                    existing.deep_dive_html = wp_action.deep_dive_html
                    existing.deep_dive_text = wp_action.deep_dive_text
                    existing.is_featured = wp_action.is_featured
                    existing.display_order = wp_action.display_order
                    existing.classifications = wp_action.classifications
                    existing.url = wp_action.url
                    existing.status = wp_action.status
                    existing.modified_at = wp_action.modified_at
                    existing.content_hash = new_hash
                    existing.ingested_at = datetime.utcnow()
                    # Content changed → invalidate this action's embeddings
                    session.execute(
                        delete(Embedding).where(
                            Embedding.content_type == "action",
                            Embedding.content_id == existing.id,
                        )
                    )

                    # If the title changed, also invalidate testimonials that reference this action
                    # (because they include the action title in their embedded text)
                    if title_changed:
                        related_testimonials = (
                            session.execute(
                                select(Testimonial.id).where(
                                    Testimonial.site_id == site_id,
                                    Testimonial.related_action_id == existing.id,
                                )
                            )
                            .scalars()
                            .all()
                        )
                        if related_testimonials:
                            session.execute(
                                delete(Embedding).where(
                                    Embedding.content_type == "testimonial",
                                    Embedding.content_id.in_(related_testimonials),
                                )
                            )
                    if not was_archived:
                        stats["updated"] += 1

        # Archive any DB records for this site that weren't in WP.
        # Skip the sweep if WP returned zero records — likely a transient issue,
        # not a real "everything was deleted" event.
        if seen_wp_post_ids:
            result = session.execute(
                update(Action)
                .where(
                    Action.site_id == site_id,
                    Action.archived_at.is_(None),
                    Action.wp_post_id.notin_(seen_wp_post_ids),
                )
                .values(archived_at=datetime.utcnow())
            )
            stats["archived"] = result.rowcount  # type: ignore[attr-defined]

    return stats


def ingest_testimonials(site_id: int) -> dict:
    """Ingest all published testimonials for a site into pgvector.

    Returns a summary dict with counts: inserted, updated, unchanged, archived, unarchived.
    """
    wp_testimonials = get_testimonials(site_id)
    stats = {
        "inserted": 0,
        "updated": 0,
        "unchanged": 0,
        "archived": 0,
        "unarchived": 0,
        "total_in_wp": len(wp_testimonials),
    }

    seen_wp_post_ids = {wp.wp_post_id for wp in wp_testimonials}

    with db_session() as session:
        for wp_testimonial in wp_testimonials:
            new_hash = _testimonial_hash(wp_testimonial)
            related_action_id = _resolve_action_id(
                session, site_id, wp_testimonial.related_action_wp_post_id
            )

            existing = session.execute(
                select(Testimonial).where(
                    Testimonial.site_id == site_id,
                    Testimonial.wp_post_id == wp_testimonial.wp_post_id,
                )
            ).scalar_one_or_none()

            if existing is None:
                session.add(
                    Testimonial(
                        site_id=site_id,
                        wp_post_id=wp_testimonial.wp_post_id,
                        title=wp_testimonial.title,
                        body_html=wp_testimonial.body_html,
                        body_text=wp_testimonial.body_text,
                        submitted_by=wp_testimonial.submitted_by,
                        display_name=wp_testimonial.display_name,
                        related_action_wp_post_id=wp_testimonial.related_action_wp_post_id,
                        related_action_id=related_action_id,
                        display_order=wp_testimonial.display_order,
                        status=wp_testimonial.status,
                        modified_at=wp_testimonial.modified_at,
                        content_hash=new_hash,
                        ingested_at=datetime.utcnow(),
                    )
                )
                stats["inserted"] += 1
            else:
                was_archived = existing.archived_at is not None
                if was_archived:
                    existing.archived_at = None
                    stats["unarchived"] += 1

                if existing.content_hash == new_hash and not was_archived:
                    stats["unchanged"] += 1
                else:
                    existing.title = wp_testimonial.title
                    existing.body_html = wp_testimonial.body_html
                    existing.body_text = wp_testimonial.body_text
                    existing.submitted_by = wp_testimonial.submitted_by
                    existing.display_name = wp_testimonial.display_name
                    existing.related_action_wp_post_id = (
                        wp_testimonial.related_action_wp_post_id
                    )
                    existing.related_action_id = related_action_id
                    existing.display_order = wp_testimonial.display_order
                    existing.status = wp_testimonial.status
                    existing.modified_at = wp_testimonial.modified_at
                    existing.content_hash = new_hash
                    existing.ingested_at = datetime.utcnow()
                    # Invalidate this testimonial's embeddings
                    session.execute(
                        delete(Embedding).where(
                            Embedding.content_type == "testimonial",
                            Embedding.content_id == existing.id,
                        )
                    )
                    if not was_archived:
                        stats["updated"] += 1

        # Archive sweep
        if seen_wp_post_ids:
            result = session.execute(
                update(Testimonial)
                .where(
                    Testimonial.site_id == site_id,
                    Testimonial.archived_at.is_(None),
                    Testimonial.wp_post_id.notin_(seen_wp_post_ids),
                )
                .values(archived_at=datetime.utcnow())
            )
            stats["archived"] = result.rowcount  # type: ignore[attr-defined]

    return stats


def ingest_events(site_id: int) -> dict:
    """Ingest all published events for a site into pgvector.

    Returns a summary dict with counts: inserted, updated, unchanged, archived, unarchived.
    """
    wp_events = get_events(site_id)
    stats = {
        "inserted": 0,
        "updated": 0,
        "unchanged": 0,
        "archived": 0,
        "unarchived": 0,
        "total_in_wp": len(wp_events),
    }

    seen_wp_post_ids = {wp.wp_post_id for wp in wp_events}

    with db_session() as session:
        for wp_event in wp_events:
            new_hash = _event_hash(wp_event)

            existing = session.execute(
                select(Event).where(
                    Event.site_id == site_id,
                    Event.wp_post_id == wp_event.wp_post_id,
                )
            ).scalar_one_or_none()

            if existing is None:
                session.add(
                    Event(
                        site_id=site_id,
                        wp_post_id=wp_event.wp_post_id,
                        title=wp_event.title,
                        description_html=wp_event.description_html,
                        description_text=wp_event.description_text,
                        start_datetime_utc=wp_event.start_datetime_utc,
                        end_datetime_utc=wp_event.end_datetime_utc,
                        start_datetime_local=wp_event.start_datetime_local,
                        end_datetime_local=wp_event.end_datetime_local,
                        timezone=wp_event.timezone,
                        venue_name=wp_event.venue_name,
                        venue_address=wp_event.venue_address,
                        organizer_names=wp_event.organizer_names,
                        organizer_emails=wp_event.organizer_emails,
                        event_url=wp_event.event_url,
                        cost=wp_event.cost,
                        status=wp_event.status,
                        modified_at=wp_event.modified_at,
                        content_hash=new_hash,
                        ingested_at=datetime.utcnow(),
                    )
                )
                stats["inserted"] += 1
            else:
                was_archived = existing.archived_at is not None
                if was_archived:
                    existing.archived_at = None
                    stats["unarchived"] += 1

                if existing.content_hash == new_hash and not was_archived:
                    stats["unchanged"] += 1
                else:
                    existing.title = wp_event.title
                    existing.description_html = wp_event.description_html
                    existing.description_text = wp_event.description_text
                    existing.start_datetime_utc = wp_event.start_datetime_utc
                    existing.end_datetime_utc = wp_event.end_datetime_utc
                    existing.start_datetime_local = wp_event.start_datetime_local
                    existing.end_datetime_local = wp_event.end_datetime_local
                    existing.timezone = wp_event.timezone
                    existing.venue_name = wp_event.venue_name
                    existing.venue_address = wp_event.venue_address
                    existing.organizer_names = wp_event.organizer_names
                    existing.organizer_emails = wp_event.organizer_emails
                    existing.event_url = wp_event.event_url
                    existing.cost = wp_event.cost
                    existing.status = wp_event.status
                    existing.modified_at = wp_event.modified_at
                    existing.content_hash = new_hash
                    existing.ingested_at = datetime.utcnow()
                    if not was_archived:
                        stats["updated"] += 1

        # Archive sweep
        if seen_wp_post_ids:
            result = session.execute(
                update(Event)
                .where(
                    Event.site_id == site_id,
                    Event.archived_at.is_(None),
                    Event.wp_post_id.notin_(seen_wp_post_ids),
                )
                .values(archived_at=datetime.utcnow())
            )
            stats["archived"] = result.rowcount  # type: ignore[attr-defined]

    return stats
