"""Anmeldung — Endpunkte.

Der verbindliche Vertrag steht in docs/auth-api.md.

- `POST /auth/login` — formular-kodiert (`OAuth2PasswordRequestForm`),
  Feld `username` enthält die E-Mail. Antwort: `TokenResponse`.
  `401` bei falscher E-Mail *oder* falschem Passwort, bewusst nicht
  unterscheidbar.
- `GET /auth/me` — liefert `UserPublic` zum Token. Steht noch aus und kommt
  zusammen mit `get_current_user` dazu (Issue #15).

Der Endpunkt übersetzt nur: Formular entgegennehmen, `service.authenticate`
fragen, Antwort in Token und Statuscode gießen. Die Prüfung selbst steht in
`service.py`, das Ausstellen des Tokens in `app.core.security`.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session

from app.core.security import create_access_token
from app.db.session import get_session
from app.modules.auth import service
from app.modules.auth.schemas import TokenResponse
from app.modules.users.schemas import UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])

SessionDep = Annotated[Session, Depends(get_session)]

# Ein einziger Wortlaut für alle Fehlerfälle. Zwei verschiedene Meldungen wären
# genau die Unterscheidung, die der Vertrag ausschließt.
INVALID_CREDENTIALS = "E-Mail oder Passwort ist falsch"


@router.post("/login", response_model=TokenResponse)
def login(
    session: SessionDep,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> TokenResponse:
    """Meldet einen Benutzer an und gibt ein JWT zurück.

    Das Formularfeld heißt aus historischen Gründen `username`, enthält bei uns
    aber die E-Mail (docs/auth-api.md).
    """
    user = service.authenticate(session, email=form.username, password=form.password)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_CREDENTIALS,
            # Gehört laut HTTP-Standard zu jedem 401 und lässt den
            # Authorize-Button in /docs richtig reagieren.
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenResponse(
        access_token=create_access_token(user.id, user.role),
        user=UserPublic.model_validate(user),
    )
