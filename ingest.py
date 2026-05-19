"""Ingestion: pull from WordPress, transform, upsert into pgvector."""

from datetime import datetime

from sqlalchemy import select, update

# from sqlalchemy.engine import CursorResult

from db import db_session
from hashing import compute_content_hash
from models import Action
from wp_repository import WPAction, get_actions


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
