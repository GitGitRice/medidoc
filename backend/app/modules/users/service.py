"""Datenbankzugriffe auf Benutzer.

Die Naht zwischen Benutzer- und Auth-Strang: Der Login holt seinen Benutzer
über diese Funktionen, statt eigene Queries zu schreiben. Ändert sich am
User-Model etwas, bleibt es damit in diesem Modul.
"""

from sqlmodel import Session, select

from app.modules.users.models import User


def get_by_email(session: Session, email: str) -> User | None:
    """Benutzer über die Login-Kennung. `None`, wenn es die E-Mail nicht gibt."""
    return session.exec(select(User).where(User.email == email)).first()


def get_by_id(session: Session, user_id: int) -> User | None:
    """Benutzer über die ID — für die Token-Prüfung.

    Die Rolle wird bewusst hier aus der Datenbank gelesen und nicht aus dem
    Token übernommen, siehe docs/auth-api.md.
    """
    return session.get(User, user_id)
