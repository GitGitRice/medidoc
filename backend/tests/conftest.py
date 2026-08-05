"""Gemeinsame Fixtures.

Die Tests laufen gegen **SQLite im Speicher**, nicht gegen Postgres: Sie sollen
ohne laufendes Docker durchgehen und sich nicht gegenseitig Daten hinterlassen.
Jeder Test bekommt eine frische, leere Datenbank.

Die App bekommt die Test-Session über `dependency_overrides` untergeschoben —
`get_session` selbst und damit auch die echte Engine bleiben unangetastet.
"""

from collections.abc import Generator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

# Nur wegen der Nebenwirkung: registriert alle Tabellen in SQLModel.metadata.
import app.db.base  # noqa: F401
from app.core.security import create_access_token, hash_password
from app.db.session import get_session
from app.main import app
from app.modules.audit.store import MemoryAuditStore, set_store
from app.modules.patients.models import Patient
from app.modules.users import service as users_service
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


@pytest.fixture(name="audit_store", autouse=True)
def audit_store_fixture() -> Generator[MemoryAuditStore, None, None]:
    """Ein leerer Audit-Trail pro Test.

    `autouse`, weil sonst der erste Test, der einen Fehlversuch auslöst, die
    Zähler für alle folgenden vorbelegt — und die Missbrauchserkennung dann
    scheinbar zufällig anschlägt. Jeder Test fängt bei null an.
    """
    store = MemoryAuditStore()
    set_store(store)

    yield store

    set_store(None)


@pytest.fixture(name="client")
def client_fixture(session: Session) -> Generator[TestClient, None, None]:
    """Ein Client, dessen Requests auf derselben Session arbeiten wie der Test."""
    app.dependency_overrides[get_session] = lambda: session

    # `raise_server_exceptions=False`: Der TestClient wirft sonst Ausnahmen aus
    # dem Server heraus, statt sie zu einer 500-Antwort werden zu lassen — und
    # dann liefe die Middleware, die genau diese 500 protokollieren soll, nie zu
    # Ende.
    yield TestClient(app, raise_server_exceptions=False)

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
            # Wie `seed.py` schreiben, sonst fände `get_by_email` einen mit
            # Großbuchstaben angelegten Testbenutzer nicht wieder.
            email=users_service.normalize_email(email),
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


@pytest.fixture(name="auth_headers")
def auth_headers_fixture():
    """Baut den Bearer-Header, den geschützte Endpunkte erwarten."""

    def _auth_headers(user: User) -> dict[str, str]:
        token = create_access_token(user.id, user.role)
        return {"Authorization": f"Bearer {token}"}

    return _auth_headers


@pytest.fixture(name="admin_headers")
def admin_headers_fixture(make_user, auth_headers) -> dict[str, str]:
    """Fertiger Header für die Tests, in denen die Rolle nicht das Thema ist.

    `admin`, weil das die Rolle ist, die alle Endpunkte erreicht. Wo die Rolle
    selbst geprüft wird, steht `staff_headers` daneben.
    """
    return auth_headers(make_user(email="anna.admin@medidoc.test", role=Role.ADMIN))


@pytest.fixture(name="staff_headers")
def staff_headers_fixture(make_user, auth_headers) -> dict[str, str]:
    """Fertiger Header für einen Benutzer ohne Löschrecht."""
    return auth_headers(
        make_user(
            email="tom.staff@medidoc.test",
            name="Tom Staff",
            role=Role.STAFF,
        )
    )


@pytest.fixture(name="make_patient")
def make_patient_fixture(session: Session):
    """Legt einen Patienten direkt in der Datenbank an.

    Bewusst an der API vorbei: Ein Test, der seinen Ausgangszustand über
    `POST /patienten` herstellt, prüft nebenbei immer auch das Anlegen mit —
    und wird rot, wenn dort etwas kaputtgeht, obwohl er von etwas anderem
    handelt.
    """

    def _make_patient(
        first_name: str = "Max",
        last_name: str = "Mustermann",
        date_of_birth: date = date(1978, 3, 14),
        **felder: object,
    ) -> Patient:
        patient = Patient(
            first_name=first_name,
            last_name=last_name,
            date_of_birth=date_of_birth,
            **felder,
        )
        session.add(patient)
        session.commit()
        session.refresh(patient)
        return patient

    return _make_patient
