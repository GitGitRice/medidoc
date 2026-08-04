"""Gemeinsame Fixtures.

Die Tests laufen gegen **SQLite im Speicher**, nicht gegen Postgres: Sie sollen
ohne laufendes Docker durchgehen und sich nicht gegenseitig Daten hinterlassen.
Jeder Test bekommt eine frische, leere Datenbank.

Die App bekommt die Test-Session über `dependency_overrides` untergeschoben —
`get_session` selbst und damit auch die echte Engine bleiben unangetastet.
"""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

# Nur wegen der Nebenwirkung: registriert alle Tabellen in SQLModel.metadata.
import app.db.base  # noqa: F401
from app.core.security import hash_password
from app.db.session import get_session
from app.main import app
from app.modules.users.models import Role, User


@pytest.fixture(name="session")
def session_fixture() -> Generator[Session, None, None]:
    """Eine leere Datenbank pro Test."""
    engine = create_engine(
        "sqlite://",
        # In-Memory-SQLite gehört sonst genau einer Verbindung. StaticPool hält
        # dieselbe für alle, sonst sieht der Request die Tabellen des Tests nicht.
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session) -> Generator[TestClient, None, None]:
    """Ein Client, dessen Requests auf derselben Session arbeiten wie der Test."""
    app.dependency_overrides[get_session] = lambda: session

    yield TestClient(app)

    app.dependency_overrides.clear()


@pytest.fixture(name="make_user")
def make_user_fixture(session: Session):
    """Legt einen Benutzer an — Passwort im Klartext rein, gehasht in die DB."""

    def _make_user(
        email: str = "anna.admin@medidoc.test",
        password: str = "geheim123",
        name: str = "Anna Admin",
        role: Role = Role.ADMIN,
        is_active: bool = True,
    ) -> User:
        user = User(
            email=email,
            name=name,
            password_hash=hash_password(password),
            role=role,
            is_active=is_active,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    return _make_user
