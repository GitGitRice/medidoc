"""Die Absicherung, die alle anderen Module benutzen.

**Strang C (Steven), noch nicht implementiert.** Das ist die wichtigste Naht im
Backend: Jedes andere Modul schützt seine Endpunkte über genau diese zwei
Dependencies und schreibt keine eigene Token-Prüfung.

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

Solange hier `NotImplementedError` steht, laufen die Patienten-Endpunkte
ungeschützt — bewusst so, siehe docs/sprint-1-plan.md. Sie werden in einem
Durchgang abgesichert, sobald diese Datei steht. Die Stubs geben absichtlich
nie einen Benutzer zurück: Ein Fehler ist harmlos, ein versehentlich
durchgewinkter Request nicht.
"""

from collections.abc import Callable

from fastapi import Depends
from sqlmodel import Session

from app.db.session import get_session
from app.modules.users.models import Role, User


def get_current_user(session: Session = Depends(get_session)) -> User:
    """Der angemeldete Benutzer zum `Authorization: Bearer <token>`-Header.

    Erwartet: Token dekodieren (`HS256`, Secret aus `settings.jwt_secret`),
    `sub` als Benutzer-ID lesen, Benutzer über
    `app.modules.users.service.get_by_id` holen, `401` wenn der Token fehlt,
    abgelaufen oder ungültig ist oder der Benutzer nicht `is_active` ist.
    """
    raise NotImplementedError("Auth steht noch aus — siehe docs/auth-api.md")


def require_roles(*allowed_roles: Role) -> Callable[..., User]:
    """Baut eine Dependency, die zusätzlich die Rolle prüft.

    Erwartet: `get_current_user` aufrufen, dann `403`, wenn die Rolle des
    Benutzers nicht in `allowed_roles` liegt.
    """

    def dependency(user: User = Depends(get_current_user)) -> User:
        raise NotImplementedError("Auth steht noch aus — siehe docs/auth-api.md")

    return dependency
