"""Verbindung und Session — die eine Stelle, an der die Engine entsteht.

Gehört allen Strängen gemeinsam. Wer eine Session braucht, nimmt `get_session`
und legt keine zweite Session-Verwaltung an.
"""

from collections.abc import Generator

from sqlmodel import Session, create_engine

from app.core.config import settings

engine = create_engine(settings.database_url, echo=False)


def get_session() -> Generator[Session, None, None]:
    """FastAPI-Dependency: eine Session pro Request."""
    with Session(engine) as session:
        yield session
