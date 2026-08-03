from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime, String
from sqlmodel import Field, SQLModel


class Role(StrEnum):
    """Siehe ADR-0005. Geprüft wird mengenbasiert, nicht als Rangfolge."""

    ADMIN = "admin"
    STAFF = "staff"


class User(SQLModel, table=True):
    """Praxispersonal, das sich anmeldet — nicht der Patient (siehe CONTEXT.md)."""

    # "user" ist in Postgres ein reserviertes Wort und müsste überall gequotet
    # werden, deshalb "users".
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    name: str
    password_hash: str
    # Als varchar gespeichert, nicht als Postgres-ENUM-Typ — eine neue Rolle
    # braucht so keine Migration, siehe ADR-0005.
    role: Role = Field(default=Role.STAFF, sa_type=String)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=DateTime(timezone=True),
    )