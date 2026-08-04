"""Die Prüfung hinter dem Login.

Kennt kein HTTP (siehe backend/README.md): Diese Datei sagt nur *ob* jemand
sich anmelden darf, nicht mit welchem Statuscode das beantwortet wird. Der
Benutzer kommt über `app.modules.users.service`, das Passwort prüft
`app.core.security` — hier stehen keine eigenen Queries und kein eigenes
Hashing.
"""

from sqlmodel import Session

from app.core.security import hash_password, verify_password
from app.modules.users import service as users_service
from app.modules.users.models import User

# Ein Hash, gegen den geprüft wird, wenn es die E-Mail gar nicht gibt. Ohne ihn
# wäre die Antwort für eine unbekannte E-Mail messbar schneller als die für ein
# falsches Passwort — und damit doch unterscheidbar, obwohl der Statuscode
# derselbe ist (docs/auth-api.md).
_DUMMY_PASSWORD_HASH = hash_password("dummy-passwort-fuer-konstante-laufzeit")


def authenticate(session: Session, email: str, password: str) -> User | None:
    """Der Benutzer zu diesen Zugangsdaten, sonst `None`.

    `None` bedeutet bewusst dreierlei auf einmal — E-Mail unbekannt, Passwort
    falsch, Benutzer deaktiviert. Der Router kann die Fälle damit gar nicht
    unterscheiden und beantwortet alle drei mit demselben `401`.
    """
    user = users_service.get_by_email(session, email)

    if user is None:
        verify_password(password, _DUMMY_PASSWORD_HASH)
        return None

    if not verify_password(password, user.password_hash):
        return None

    # Deaktivierte Benutzer können sich nicht anmelden, siehe docs/auth-api.md.
    if not user.is_active:
        return None

    return user
