"""Database engine and session factory used across the application."""

from collections.abc import Iterator

from sqlmodel import Session, create_engine

from src.runtime.config import get_config

main_config = get_config()

engine = create_engine(main_config.database_url, echo=False)


def session() -> Session:
    """Return a new SQLModel session bound to the shared engine."""
    return Session(engine, expire_on_commit=False)


def session_scope() -> Iterator[Session]:
    """Context manager style helper for repositories and tests."""
    db = session()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
