"""Connection layer for the pgvector database."""

import os
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def _build_db_url() -> str:
    return (
        f"postgresql+psycopg://{os.environ['DB_USER']}:{os.environ['DB_PASSWORD']}"
        f"@{os.environ['DB_HOST']}:{os.environ['DB_PORT']}/{os.environ['DB_NAME']}"
    )


@lru_cache(maxsize=1)
def _get_engine() -> Engine:
    """Build the SQLAlchemy engine once, cache it for reuse."""
    return create_engine(_build_db_url(), echo=False)


@lru_cache(maxsize=1)
def _get_session_factory() -> sessionmaker[Session]:
    """Build the session factory once, cache it for reuse."""
    return sessionmaker(bind=_get_engine(), expire_on_commit=False)


@contextmanager
def db_session():
    """Context manager that yields a SQLAlchemy session and handles commit/rollback."""
    session = _get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()