"""Passwörter und Token — die kryptografischen Handgriffe, sonst nichts.

Fachlich neutral und ohne Datenbank: Wer hier hereinkommt, hat den Benutzer
schon. Die Frage *ob* jemand sich anmelden darf, beantwortet
`app.modules.auth.service`.
"""

from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import settings

# bcrypt liest nur die ersten 72 Bytes eines Passworts und wirft darüber einen
# Fehler, statt still abzuschneiden. Hier abgefangen, damit ein zu langes
# Passwort beim Anlegen auffällt und nicht erst beim Login.
MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    """Hasht ein Klartext-Passwort. Das Ergebnis enthält seinen eigenen Salt."""
    _check_length(password)
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """Vergleicht Klartext gegen gespeicherten Hash, in konstanter Zeit."""
    if len(password.encode()) > MAX_PASSWORD_BYTES:
        return False
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_access_token(user_id: int, role: str) -> str:
    """Stellt das JWT aus, das der Login zurückgibt.

    Form und Laufzeit stehen in docs/auth-api.md: `HS256`, acht Stunden, kein
    Refresh-Token. Die Rolle liegt im Token, damit das Frontend die Oberfläche
    danach richten kann — geprüft wird sie im Backend trotzdem bei jedem
    Request neu aus der Datenbank.
    """
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        # "sub" muss laut JWT-Standard ein String sein, die ID ist ein int.
        "sub": str(user_id),
        "role": str(role),
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, object] | None:
    """Prüft und dekodiert ein Access-Token, sonst `None`.

    Ungültige Signaturen, abgelaufene Token und eine unpassende Payload sind
    für die aufrufende Auth-Schicht derselbe Fall: Es gibt keine bestätigte
    Identität.
    """
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "role", "exp"]},
        )
    except jwt.InvalidTokenError:
        return None


def _check_length(password: str) -> None:
    if len(password.encode()) > MAX_PASSWORD_BYTES:
        raise ValueError(
            f"Passwort darf hoechstens {MAX_PASSWORD_BYTES} Bytes lang sein."
        )
