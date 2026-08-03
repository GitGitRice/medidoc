"""Startbenutzer anlegen.

Aufruf aus backend/:  python -m app.seed

Mehrfach ausführbar — vorhandene Benutzer werden übersprungen, nicht überschrieben.
Die Zugangsdaten stehen in der .env im Repo-Wurzelverzeichnis. Reine Testdaten.
"""

from sqlmodel import Session, select

from app.config import settings
from app.db import engine, init_db
from app.models import Role, User
from app.security import hash_password


def create_user(
    session: Session, email: str, name: str, password: str, role: Role
) -> bool:
    """Legt einen Benutzer an. False, wenn die E-Mail schon vergeben ist."""
    existing = session.exec(select(User).where(User.email == email)).first()
    if existing:
        return False

    session.add(
        User(
            email=email,
            name=name,
            password_hash=hash_password(password),
            role=role,
        )
    )
    return True


def seed() -> None:
    init_db()

    initial_users = [
        (settings.seed_admin_email, "Anna Admin", settings.seed_admin_password, Role.ADMIN),
        (settings.seed_staff_email, "Tom Staff", settings.seed_staff_password, Role.STAFF),
    ]

    with Session(engine) as session:
        for email, name, password, role in initial_users:
            if create_user(session, email, name, password, role):
                print(f"created:  {email} ({role})")
            else:
                print(f"exists:   {email} ({role})")
        session.commit()


if __name__ == "__main__":
    seed()
