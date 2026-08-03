import bcrypt

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


def _check_length(password: str) -> None:
    if len(password.encode()) > MAX_PASSWORD_BYTES:
        raise ValueError(
            f"Passwort darf hoechstens {MAX_PASSWORD_BYTES} Bytes lang sein."
        )
