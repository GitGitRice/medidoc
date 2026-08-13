"""Was der Login zurückgibt.

Die Form ist in docs/auth-api.md festgelegt und das Frontend baut darauf —
Änderungen hier gehören ins Daily.
"""

from sqlmodel import SQLModel

from app.modules.users.schemas import UserPublic


class TokenResponse(SQLModel):
    """Antwort auf `POST /auth/login`.

    Der Benutzer kommt gleich mit, damit das Frontend nach dem Login keinen
    zweiten Request braucht.
    """

    access_token: str
    token_type: str = "bearer"
    user: UserPublic
