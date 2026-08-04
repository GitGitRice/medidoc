"""Was von einem Benutzer über die API geht.

Getrennt vom Model, weil die Tabelle Felder hat, die nach außen nie auftauchen
dürfen — allen voran `password_hash`.
"""

from sqlmodel import SQLModel

from app.modules.users.models import Role


class UserPublic(SQLModel):
    """Response-Model: alles, was ein Benutzer nach außen sein darf.

    Bewusst ohne `password_hash`. Endpunkte geben dieses Model zurück, niemals
    `User` selbst.
    """

    id: int
    email: str
    name: str
    role: Role
