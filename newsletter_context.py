"""Gather all content needed to draft a newsletter for a community."""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select

from db import db_session
from embedding_client import embed_texts
from models import Action, Embedding, Event, Testimonial


@dataclass
class NewsletterContext:
    """Everything we'll hand to the LLM for newsletter generation."""

    site_id: int
    community_name: str
    theme: str | None
    featured_actions: list[Action] = field(default_factory=list)
    theme_actions: list[Action] = field(default_factory=list)
    testimonials_by_action: dict[str, list[Testimonial]] = field(default_factory=dict)
    upcoming_events: list[Event] = field(default_factory=list)


def gather_newsletter_context(
    site_id: int,
    community_name: str,
    theme: str | None = None,
    max_theme_actions: int = 5,
    max_events: int = 5,
) -> NewsletterContext:
    """Pull all the content needed to draft a newsletter.

    Combines structured queries (featured actions, upcoming events, linked
    testimonials) with semantic search (theme-relevant actions) so each
    technique is used where it works best.
    """
    context = NewsletterContext(
        site_id=site_id,
        community_name=community_name,
        theme=theme,
    )

    with db_session() as session:
        # Featured actions — structured query, always include all of them
        featured = (
            session.execute(
                select(Action)
                .where(
                    Action.site_id == site_id,
                    Action.archived_at.is_(None),
                    Action.is_featured.is_(True),
                )
                .order_by(Action.display_order.asc().nulls_last())
            )
            .scalars()
            .all()
        )
        context.featured_actions = list(featured)
        featured_ids = {a.id for a in featured}

        # Theme-relevant actions — semantic search if theme given,
        # otherwise top by display_order
        if theme:
            query_vec = embed_texts([theme], input_type="query")[0]

            candidates = session.execute(
                select(
                    Embedding.content_id,
                    Embedding.embedding.cosine_distance(query_vec).label("distance"),
                )
                .where(
                    Embedding.site_id == site_id,
                    Embedding.content_type == "action",
                )
                .order_by("distance")
                .limit(max_theme_actions * 4)
            ).all()

            # Collapse to best-distance per action, exclude featured
            best_per_action: dict[str, float] = {}
            for row in candidates:
                aid = str(row.content_id)
                if aid in featured_ids:
                    continue
                if aid not in best_per_action:
                    best_per_action[aid] = row.distance

            top_action_ids = sorted(best_per_action.items(), key=lambda x: x[1])[
                :max_theme_actions
            ]

            if top_action_ids:
                action_records = (
                    session.execute(
                        select(Action).where(
                            Action.id.in_([aid for aid, _ in top_action_ids]),
                            Action.archived_at.is_(None),
                        )
                    )
                    .scalars()
                    .all()
                )
                # Preserve order by distance
                by_id = {str(a.id): a for a in action_records}
                context.theme_actions = [
                    by_id[aid] for aid, _ in top_action_ids if aid in by_id
                ]
        else:
            # Build the query without the notin filter if there are no featured ids
            theme_query = select(Action).where(
                Action.site_id == site_id,
                Action.archived_at.is_(None),
            )
            if featured_ids:
                theme_query = theme_query.where(Action.id.notin_(featured_ids))
            theme_query = theme_query.order_by(
                Action.display_order.asc().nulls_last()
            ).limit(max_theme_actions)

            theme_actions = session.execute(theme_query).scalars().all()
            context.theme_actions = list(theme_actions)

        # Testimonials linked to all chosen actions — structured query
        all_action_ids = [
            a.id for a in context.featured_actions + context.theme_actions
        ]
        if all_action_ids:
            testimonials = (
                session.execute(
                    select(Testimonial)
                    .where(
                        Testimonial.site_id == site_id,
                        Testimonial.archived_at.is_(None),
                        Testimonial.related_action_id.in_(all_action_ids),
                    )
                    .order_by(Testimonial.display_order.asc().nulls_last())
                )
                .scalars()
                .all()
            )

            by_action: dict[str, list[Testimonial]] = {}
            for t in testimonials:
                if t.related_action_id is None:
                    continue
                key = str(t.related_action_id)
                by_action.setdefault(key, []).append(t)
            context.testimonials_by_action = by_action

        # Upcoming events — structured query, filtered by date
        now = datetime.now(timezone.utc)
        events = (
            session.execute(
                select(Event)
                .where(
                    Event.site_id == site_id,
                    Event.archived_at.is_(None),
                    Event.start_datetime_utc > now,
                )
                .order_by(Event.start_datetime_utc.asc())
                .limit(max_events)
            )
            .scalars()
            .all()
        )
        context.upcoming_events = list(events)

    return context
