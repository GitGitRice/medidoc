"""Anmeldung — Endpunkte.

Der verbindliche Vertrag steht in docs/auth-api.md.

- `POST /auth/login` — formular-kodiert (`OAuth2PasswordRequestForm`),
  Feld `username` enthält die E-Mail. Antwort: `TokenResponse`.
  `401` bei falscher E-Mail *oder* falschem Passwort, bewusst nicht
  unterscheidbar.
- `GET /auth/me` — liefert `UserPublic` zum gültigen Bearer-Token.

Der Endpunkt übersetzt nur: Formular entgegennehmen, `service.authenticate`
fragen, Antwort in Token und Statuscode gießen. Die Prüfung selbst steht in
`service.py`, das Ausstellen des Tokens in `app.core.security`.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session

from app.core.security import create_access_token
from app.db.session import get_session
from app.modules.audit import service as audit
from app.modules.audit.events import EventType
from app.modules.auth import service
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import TokenResponse
from app.modules.users import service as users_service
from app.modules.users.models import User
from app.modules.users.schemas import UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])

SessionDep = Annotated[Session, Depends(get_session)]

# Ein einziger Wortlaut für alle Fehlerfälle. Zwei verschiedene Meldungen wären
# genau die Unterscheidung, die der Vertrag ausschließt.
INVALID_CREDENTIALS = "E-Mail oder Passwort ist falsch"


@router.post("/login", response_model=TokenResponse)
def login(
    request: Request,
    session: SessionDep,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> TokenResponse:
    """Meldet einen Benutzer an und gibt ein JWT zurück.

    Das Formularfeld heißt aus historischen Gründen `username`, enthält bei uns
    aber die E-Mail (docs/auth-api.md).
    """
    user = service.authenticate(session, email=form.username, password=form.password)

    # Beide Ausgänge landen im Audit-Trail. Der fehlgeschlagene Versuch wird
    # hier festgehalten und nicht in der Middleware, weil nur an dieser Stelle
    # bekannt ist, *welches Konto* gemeint war — die Antwort verrät es bewusst
    # nicht. Das Passwort wird nirgends mitgegeben; die versuchte E-Mail
    # normalisiert, damit "Anna@…" und "anna@…" als derselbe Versuch zählen.
    if user is None:
        audit.record(
            EventType.LOGIN_FAILED,
            request=request,
            email=users_service.normalize_email(form.username),
            status=status.HTTP_401_UNAUTHORIZED,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_CREDENTIALS,
            # Gehört laut HTTP-Standard zu jedem 401 und lässt den
            # Authorize-Button in /docs richtig reagieren.
            headers={"WWW-Authenticate": "Bearer"},
        )

    audit.record(
        EventType.LOGIN_SUCCEEDED,
        request=request,
        email=user.email,
        user_id=user.id,
        status=status.HTTP_200_OK,
    )

    return TokenResponse(
        access_token=create_access_token(user.id, user.role),
        user=UserPublic.model_validate(user),
    )


@router.get("/me", response_model=UserPublic)
def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    """Liefert den zum Bearer-Token gehörenden aktiven Benutzer."""
    return user
