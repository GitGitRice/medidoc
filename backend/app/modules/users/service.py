"""Datenbankzugriffe auf Benutzer.

Die Naht zwischen Benutzer- und Auth-Strang: Der Login holt seinen Benutzer
über diese Funktionen, statt eigene Queries zu schreiben. Ändert sich am
User-Model etwas, bleibt es damit in diesem Modul.
"""

from sqlmodel import Session, select

from app.core.security import hash_password
from app.modules.users.models import User
from app.modules.users.schemas import UserCreate, UserUpdate


def normalize_email(email: str) -> str:
    """Die eine Schreibweise, in der eine E-Mail gespeichert und gesucht wird.

    `User.email` ist in Postgres case-sensitiv eindeutig. Ohne diese Regel
    würden `Anna.Admin@…` und `anna.admin@…` zwei Konten werden und ein Login
    mit der "falschen" Schreibweise still ins Leere greifen. Deshalb gilt:
    normalisiert schreiben (siehe `seed.py`), normalisiert suchen.
    """
    return email.strip().lower()


def get_by_email(session: Session, email: str) -> User | None:
    """Benutzer über die Login-Kennung. `None`, wenn es die E-Mail nicht gibt.

    Normalisiert selbst, damit kein Aufrufer daran denken muss.
    """
    return session.exec(
        select(User).where(User.email == normalize_email(email))
    ).first()


def create(session: Session, data: UserCreate) -> User:
    """Legt einen Benutzer an und hasht dabei sein Passwort.

    Die E-Mail wird normalisiert gespeichert — dieselbe Regel wie im Seed,
    sonst könnte sich der Angelegte mit seiner eigenen Schreibweise nicht
    anmelden.
    """
    user = User(
        email=normalize_email(data.email),
        name=data.name,
        password_hash=hash_password(data.password),
        role=data.role,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def update(session: Session, user: User, data: UserUpdate) -> User:
    """Setzt nur die Felder, die tatsächlich mitgeschickt wurden.

    `exclude_unset`, damit ein weggelassenes Feld unverändert bleibt und nicht
    auf seinen Default zurückfällt — sonst würde ein reiner Rollenwechsel
    nebenbei `is_active` überschreiben.
    """
    for feld, wert in data.model_dump(exclude_unset=True).items():
        setattr(user, feld, wert)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def get_by_id(session: Session, user_id: int) -> User | None:
    """Benutzer über die ID — für die Token-Prüfung.

    Die Rolle wird bewusst hier aus der Datenbank gelesen und nicht aus dem
    Token übernommen, siehe docs/auth-api.md.
    """
    return session.get(User, user_id)
