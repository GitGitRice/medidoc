"""Die Absicherung, die alle anderen Module benutzen.

Jedes andere Modul schützt seine Endpunkte über genau diese zwei Dependencies
und schreibt keine eigene Token-Prüfung.

    # nur angemeldet
    @router.get("/patients")
    def list_patients(user: User = Depends(get_current_user)): ...

    # angemeldet und in der erlaubten Rollenmenge
    @router.delete("/patients/{patient_id}")
    def delete_patient(user: User = Depends(require_roles(Role.ADMIN))): ...

Geprüft wird mengenbasiert, nicht als Rangfolge — Begründung in ADR-0005.
`401` heißt "nicht angemeldet", `403` heißt "Rolle reicht nicht"; die
Unterscheidung ist für das Frontend wichtig, siehe docs/auth-api.md.

Die Rolle wird bei jeder Prüfung aus der Datenbank gelesen und nicht aus dem
Token übernommen, damit ein noch acht Stunden gültiger Token nach einer
Rollenänderung keine alten Rechte mitschleppt.
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session

from app.core.security import decode_access_token
from app.db.session import get_session
from app.modules.users import service as users_service
from app.modules.users.models import Role, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

UNAUTHORIZED_DETAIL = "Anmeldung erforderlich"


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=UNAUTHORIZED_DETAIL,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    session: Session = Depends(get_session),
) -> User:
    """Der angemeldete Benutzer zum `Authorization: Bearer <token>`-Header.

    Dekodiert den Token, liest `sub` als Benutzer-ID und holt den Benutzer über
    `app.modules.users.service.get_by_id`. Antwortet mit `401`, wenn der Token
    fehlt, abgelaufen oder ungültig ist oder der Benutzer nicht `is_active` ist.
    """
    if token is None:
        raise _unauthorized()

    payload = decode_access_token(token)
    if payload is None:
        raise _unauthorized()

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise _unauthorized() from None

    user = users_service.get_by_id(session, user_id)
    if user is None or not user.is_active:
        raise _unauthorized()

    return user


def require_roles(*allowed_roles: Role) -> Callable[..., User]:
    """Baut eine Dependency, die zusätzlich die Rolle prüft.

    Ruft `get_current_user` auf und antwortet mit `403`, wenn die Rolle des
    Benutzers nicht in der erlaubten Menge liegt.
    """

    allowed = frozenset(allowed_roles)

    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Dazu fehlt dir die Berechtigung",
            )
        return user

    return dependency
