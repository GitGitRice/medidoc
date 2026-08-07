"""Was von einem Benutzer über die API geht.

Getrennt vom Model, weil die Tabelle Felder hat, die nach außen nie auftauchen
dürfen — allen voran `password_hash`.
"""

from pydantic import field_validator
from sqlmodel import SQLModel

from app.core.security import MAX_PASSWORD_BYTES
from app.modules.users.models import Role


class UserCreate(SQLModel):
    """Was ein `admin` beim Anlegen mitschickt.

    Das Passwort kommt im Klartext herein und wird nie so gespeichert — der
    Endpunkt hasht es, bevor der Benutzer in die Datenbank geht.
    """

    email: str
    name: str
    password: str
    role: Role = Role.STAFF

    @field_validator("email", "name")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("darf nicht leer sein")
        return cleaned

    @field_validator("password")
    @classmethod
    def _password_usable(cls, value: str) -> str:
        """Fängt hier ab, was `hash_password` sonst als 500 werfen würde.

        bcrypt liest nur die ersten 72 Bytes und wirft darüber — ein zu langes
        Passwort soll als `422` am Endpunkt auffallen, nicht als Serverfehler.
        """
        if len(value.encode()) > MAX_PASSWORD_BYTES:
            raise ValueError(f"darf höchstens {MAX_PASSWORD_BYTES} Bytes lang sein")
        return value


class UserPublic(SQLModel):
    """Response-Model: alles, was ein Benutzer nach außen sein darf.

    Bewusst ohne `password_hash`. Endpunkte geben dieses Model zurück, niemals
    `User` selbst.
    """

    id: int
    email: str
    name: str
    role: Role


class UserAdminView(UserPublic):
    """Dieselben Felder plus `is_active` — nur für die Benutzerverwaltung.

    Bewusst nicht in `UserPublic` aufgenommen: Das ist die Form, die Login und
    `/auth/me` an das Frontend liefern, und die steht als Vertrag in
    docs/auth-api.md. Ein deaktivierter Benutzer kommt dort nie an, das Feld
    wäre also überall `true` und nur Ballast.
    """

    is_active: bool


class UserUpdate(SQLModel):
    """Was ein `admin` an einem bestehenden Benutzer ändern darf.

    Beide Felder sind optional: Mitgeschickt wird nur, was sich ändern soll.
    E-Mail, Name und Passwort stehen bewusst nicht hier — Issue #50 deckt
    anlegen, deaktivieren und Rolle ändern ab, mehr nicht.
    """

    is_active: bool | None = None
    role: Role | None = None
