from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

engine = create_engine(settings.database_url, echo=False)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency: one session per request."""
    with Session(engine) as session:
        yield session


def init_db() -> None:
    """Create all tables.

    Every model module must be imported before this runs, otherwise its table is
    missing from SQLModel.metadata. Called from the seed script, not on startup —
    the app should still boot when Postgres is down.
    """
    SQLModel.metadata.create_all(engine)
