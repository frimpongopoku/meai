"""HTTP API for the MassEnergize AI service.

Wraps the existing generation and ingestion code as REST endpoints
for the WordPress plugin (and any other client) to call.
"""

import os
from datetime import datetime
from datetime import timezone

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from generate import generate_newsletter
from ingest import ingest_actions, ingest_events, ingest_testimonials
from embed import embed_actions, embed_events, embed_testimonials
from sqlalchemy import select, func
from db import db_session
from models import Action, Event, Testimonial


class FreshnessResponse(BaseModel):
    site_id: int
    last_synced_at: str | None
    counts: dict


app = FastAPI(title="MassEnergize AI Service", version="0.1.0")


# Simple shared-secret auth. The WP plugin sends this in a header;
# we compare against the env var. Good enough for v1 — same security
# model as 90% of internal HTTP services.
API_KEY_HEADER = "X-API-Key"


def require_auth(api_key: str | None) -> None:
    """Raise 401 if the request didn't include the right key."""
    expected = os.environ.get("API_KEY")
    if not expected:
        raise HTTPException(500, "Server misconfigured: no API_KEY set")
    if not api_key or api_key != expected:
        raise HTTPException(401, "Invalid or missing API key")


# === Request/response models ===


class GenerateRequest(BaseModel):
    site_id: int
    community_name: str
    theme: str | None = None


class GenerateResponse(BaseModel):
    draft: dict
    model: str
    input_tokens: int
    output_tokens: int
    generated_at: str


class IngestResponse(BaseModel):
    site_id: int
    started_at: str
    actions: dict
    testimonials: dict
    events: dict
    embeddings: dict


# === Endpoints ===


@app.get("/api/v1/health")
def health():
    """Quick liveness check. No auth required."""
    return {"ok": True, "service": "massenergize-ai", "version": "0.1.0"}


@app.post("/api/v1/generate", response_model=GenerateResponse)
def generate(
    request: GenerateRequest,
    x_api_key: str | None = Header(None, alias=API_KEY_HEADER),
):
    """Generate a newsletter draft for the given community."""
    require_auth(x_api_key)

    draft = generate_newsletter(
        site_id=request.site_id,
        community_name=request.community_name,
        theme=request.theme,
    )

    return GenerateResponse(
        draft=draft.parsed,
        model=draft.model,
        input_tokens=draft.input_tokens,
        output_tokens=draft.output_tokens,
        generated_at=datetime.utcnow().isoformat() + "Z",
    )


@app.post("/api/v1/ingest", response_model=IngestResponse)
def ingest(
    site_id: int,
    x_api_key: str | None = Header(None, alias=API_KEY_HEADER),
):
    """Ingest WP content and refresh embeddings for a site.

    Runs synchronously for v1. Takes 30-90 seconds depending on
    content volume. The plugin should show a spinner.
    """
    require_auth(x_api_key)
    started = datetime.utcnow().isoformat() + "Z"

    action_stats = ingest_actions(site_id)
    testimonial_stats = ingest_testimonials(site_id)
    event_stats = ingest_events(site_id)

    embed_action_stats = embed_actions(site_id)
    embed_testimonial_stats = embed_testimonials(site_id)
    embed_event_stats = embed_events(site_id)

    return IngestResponse(
        site_id=site_id,
        started_at=started,
        actions=action_stats,
        testimonials=testimonial_stats,
        events=event_stats,
        embeddings={
            "actions": embed_action_stats,
            "testimonials": embed_testimonial_stats,
            "events": embed_event_stats,
        },
    )


@app.get("/api/v1/freshness", response_model=FreshnessResponse)
def freshness(
    site_id: int,
    x_api_key: str | None = Header(None, alias=API_KEY_HEADER),
):
    """When was this site's content last ingested?"""
    require_auth(x_api_key)

    with db_session() as session:
        max_action = session.execute(
            select(func.max(Action.ingested_at)).where(Action.site_id == site_id)
        ).scalar()
        max_testimonial = session.execute(
            select(func.max(Testimonial.ingested_at)).where(
                Testimonial.site_id == site_id
            )
        ).scalar()
        max_event = session.execute(
            select(func.max(Event.ingested_at)).where(Event.site_id == site_id)
        ).scalar()

        action_count = (
            session.execute(
                select(func.count(Action.id)).where(
                    Action.site_id == site_id,
                    Action.archived_at.is_(None),
                )
            ).scalar()
            or 0
        )
        testimonial_count = (
            session.execute(
                select(func.count(Testimonial.id)).where(
                    Testimonial.site_id == site_id,
                    Testimonial.archived_at.is_(None),
                )
            ).scalar()
            or 0
        )
        event_count = (
            session.execute(
                select(func.count(Event.id)).where(
                    Event.site_id == site_id,
                    Event.archived_at.is_(None),
                )
            ).scalar()
            or 0
        )

    # Most recent of the three timestamps
    timestamps = [t for t in [max_action, max_testimonial, max_event] if t is not None]
    if timestamps:
        most_recent = max(timestamps)
        # Ensure UTC marker is present
        if most_recent.tzinfo is None:
            most_recent = most_recent.replace(tzinfo=timezone.utc)
        last_synced = most_recent.isoformat()
    else:
        last_synced = None

    return FreshnessResponse(
        site_id=site_id,
        last_synced_at=last_synced,
        counts={
            "actions": action_count,
            "testimonials": testimonial_count,
            "events": event_count,
        },
    )
