from datetime import datetime
from uuid import uuid4
from sqlalchemy.dialects.postgresql import ARRAY, UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pgvector.sqlalchemy import Vector


class Base(DeclarativeBase):
    pass


class Action(Base):
    __tablename__ = "actions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    site_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    wp_post_id: Mapped[int] = mapped_column(Integer, nullable=False)

    title: Mapped[str] = mapped_column(String, nullable=False)
    description_html: Mapped[str | None] = mapped_column(Text)
    description_text: Mapped[str | None] = mapped_column(Text)
    steps_to_take_html: Mapped[str | None] = mapped_column(Text)
    steps_to_take_text: Mapped[str | None] = mapped_column(Text)
    deep_dive_html: Mapped[str | None] = mapped_column(Text)
    deep_dive_text: Mapped[str | None] = mapped_column(Text)

    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    display_order: Mapped[int | None] = mapped_column(Integer)

    # category: Mapped[str | None] = mapped_column(String)
    # sub_category: Mapped[str | None] = mapped_column(String)
    classifications: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list, server_default="{}"
    )

    url: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, nullable=False)
    modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    content_hash: Mapped[str | None] = mapped_column(String)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("site_id", "wp_post_id", name="uq_actions_site_post"),
        Index(
            "idx_actions_classifications",
            "classifications",
            postgresql_using="gin",
        ),
    )


class Testimonial(Base):
    __tablename__ = "testimonials"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    site_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    wp_post_id: Mapped[int] = mapped_column(Integer, nullable=False)

    title: Mapped[str | None] = mapped_column(String)
    body_html: Mapped[str | None] = mapped_column(Text)
    body_text: Mapped[str | None] = mapped_column(Text)

    submitted_by: Mapped[str | None] = mapped_column(String)
    display_name: Mapped[str | None] = mapped_column(String)

    related_action_wp_post_id: Mapped[int | None] = mapped_column(Integer)
    related_action_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("actions.id", ondelete="SET NULL")
    )

    display_order: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, nullable=False)
    modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    content_hash: Mapped[str | None] = mapped_column(String)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("site_id", "wp_post_id", name="uq_testimonials_site_post"),
        Index("idx_testimonials_action", "related_action_id"),
    )


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    site_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    wp_post_id: Mapped[int] = mapped_column(Integer, nullable=False)

    title: Mapped[str] = mapped_column(String, nullable=False)
    description_html: Mapped[str | None] = mapped_column(Text)
    description_text: Mapped[str | None] = mapped_column(Text)

    start_datetime_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_datetime_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    start_datetime_local: Mapped[datetime | None] = mapped_column(DateTime)
    end_datetime_local: Mapped[datetime | None] = mapped_column(DateTime)
    timezone: Mapped[str | None] = mapped_column(String)

    venue_name: Mapped[str | None] = mapped_column(String)
    venue_address: Mapped[str | None] = mapped_column(String)
    organizer_names: Mapped[str | None] = mapped_column(String)
    organizer_emails: Mapped[str | None] = mapped_column(String)

    event_url: Mapped[str | None] = mapped_column(String)
    cost: Mapped[str | None] = mapped_column(String)

    status: Mapped[str] = mapped_column(String, nullable=False)
    modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    content_hash: Mapped[str | None] = mapped_column(String)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("site_id", "wp_post_id", name="uq_events_site_post"),
        Index("idx_events_upcoming", "site_id", "start_datetime_utc"),
    )


class Embedding(Base):
    __tablename__ = "embeddings"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    content_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    content_id: Mapped[str] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536))

    embedding_model: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint(
            "content_type",
            "content_id",
            "chunk_index",
            name="uq_embeddings_content_chunk",
        ),
    )
