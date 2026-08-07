"""Benutzerverwaltung — Endpunkte.

Anlegen, Deaktivieren und Rolle ändern. Alles hier verlangt `admin`
(ADR-0005); die Prüfung hängt am Router und nicht an den einzelnen Funktionen,
damit ein neuer Endpunkt nicht versehentlich ungeschützt bleibt — dieselbe
Begründung wie in `patients/router.py`.

Ein Benutzer wird **nie hart gelöscht**, sondern deaktiviert: Der Audit-Trail
verweist auf Benutzer-IDs, und eine ID, zu der es keine Zeile mehr gibt, macht
den Trail unlesbar (ADR-0005, `docs/sprint-2-plan.md`).

Pfad und JSON-Keys sind englisch, deutsch sind nur Kommentare und Doku.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.core.errors import ErrorResponse
from app.db.session import get_session
from app.modules.auth.dependencies import require_roles
from app.modules.users import service
from app.modules.users.models import Role, User
from app.modules.users.schemas import (
    UserAdminView,
    UserCreate,
    UserUpdate,
)

router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(require_roles(Role.ADMIN))],
)

SessionDep = Annotated[Session, Depends(get_session)]
# Wer den Request stellt — gebraucht für die Sperre gegen das eigene Konto. Die
# Dependency am Router prüft die Rolle, gibt den Benutzer aber nicht heraus.
AdminUser = Annotated[User, Depends(require_roles(Role.ADMIN))]

# Einmal beschrieben, an jedem Endpunkt wiederverwendet — wie in
# `patients/router.py`, sonst driften die Beschreibungen in `/docs` auseinander.
UNAUTHORIZED = {"model": ErrorResponse, "description": "Nicht angemeldet"}
FORBIDDEN = {"model": ErrorResponse, "description": "Rolle reicht nicht"}
NOT_FOUND = {"model": ErrorResponse, "description": "Benutzer nicht gefunden"}
CONFLICT = {"model": ErrorResponse, "description": "E-Mail bereits vergeben"}
SELF_LOCKOUT = {"model": ErrorResponse, "description": "Sperre des eigenen Kontos"}
UNPROCESSABLE = {"model": ErrorResponse, "description": "Eingabe ungültig"}


@router.post(
    "",
    response_model=UserAdminView,
    status_code=status.HTTP_201_CREATED,
    summary="Benutzer anlegen",
    responses={
        401: UNAUTHORIZED,
        403: FORBIDDEN,
        409: CONFLICT,
        422: UNPROCESSABLE,
    },
)
def create_user(session: SessionDep, data: UserCreate) -> User:
    """Legt einen Benutzer an und gibt ihn ohne sein Passwort zurück.

    Es gibt keine Selbstregistrierung — ein Benutzer entsteht nur hier oder
    über den Seed (ADR-0005).
    """
    _reject_taken_email(session, data.email)
    return service.create(session, data)


@router.patch(
    "/{user_id}",
    response_model=UserAdminView,
    summary="Benutzer deaktivieren oder Rolle ändern",
    responses={
        401: UNAUTHORIZED,
        403: FORBIDDEN,
        404: NOT_FOUND,
        409: SELF_LOCKOUT,
        422: UNPROCESSABLE,
    },
)
def update_user(
    session: SessionDep, aufrufer: AdminUser, user_id: int, data: UserUpdate
) -> User:
    """Ändert nur die mitgeschickten Felder und gibt den ganzen Benutzer zurück.

    `is_active: false` ist das Deaktivieren — die Zeile bleibt in der Datenbank
    stehen, der Zugang ist ab sofort zu. `role` setzt die Rolle neu; sie greift
    beim nächsten Request, weil `get_current_user` die Rolle ohnehin aus der
    Datenbank liest und nicht aus dem Token.
    """
    user = _get_or_404(session, user_id)
    _reject_self_lockout(aufrufer, user, data)
    return service.update(session, user, data)


def _reject_self_lockout(aufrufer: User, ziel: User, data: UserUpdate) -> None:
    """Verhindert, dass ein `admin` sich selbst die Verwaltung zusperrt.

    Nur das eigene Konto ist geschützt, nicht die Rolle: Einen *anderen* Admin
    darf ein Admin deaktivieren oder herabstufen. Der Fall, den das hier
    abfängt, ist der Fehlklick auf der eigenen Zeile — danach käme niemand mehr
    an die Benutzerverwaltung heran außer über den Seed (ADR-0005).
    """
    if aufrufer.id != ziel.id:
        return

    if data.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Du kannst dein eigenes Konto nicht deaktivieren",
        )
    if data.role is not None and data.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Du kannst dir selbst die Administratorrolle nicht entziehen",
        )


def _get_or_404(session: Session, user_id: int) -> User:
    """Der Benutzer, oder ein `404`, das die gesuchte ID nennt."""
    user = service.get_by_id(session, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Benutzer mit der ID {user_id} wurde nicht gefunden",
        )
    return user


def _reject_taken_email(session: Session, email: str) -> None:
    """409 statt eines 500 aus dem Unique-Index der Datenbank.

    Der Index bleibt die eigentliche Absicherung — diese Prüfung liefert nur
    die verständlichere Meldung. `get_by_email` normalisiert selbst, damit
    `Anna@…` und `anna@…` als dieselbe Kennung gelten.
    """
    if service.get_by_email(session, email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Die E-Mail {email} ist bereits einem Benutzer zugeordnet",
        )
