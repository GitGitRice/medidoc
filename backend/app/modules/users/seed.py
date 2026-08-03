"""Startbenutzer.

Es gibt keine Selbstregistrierung — Benutzer entstehen in Sprint 1 nur hier.
Die Zugangsdaten stehen in der `.env` im Repo-Wurzelverzeichnis, siehe
docs/auth-api.md. Reine Testdaten.
"""

from sqlmodel import Session

from app.core.config import settings
from app.core.security import hash_password
from app.modules.users import service
from app.modules.users.models import Role, User


def seed_users(session: Session) -> None:
    """Legt die Startbenutzer an. Vorhandene bleiben unangetastet."""
    initial_users = [
        (settings.seed_admin_email, "Anna Admin", settings.seed_admin_password, Role.ADMIN),
        (settings.seed_staff_email, "Tom Staff", settings.seed_staff_password, Role.STAFF),
    ]

    for email, name, password, role in initial_users:
        if service.get_by_email(session, email):
            print(f"users     exists:  {email} ({role})")
            continue

        session.add(
            User(
                email=email,
                name=name,
                password_hash=hash_password(password),
                role=role,
            )
        )
        print(f"users     created: {email} ({role})")
