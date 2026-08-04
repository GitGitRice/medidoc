"""Der Patient — die zentrale Einheit der Anwendung (siehe CONTEXT.md).

Hier stehen nur die Stammdaten: die beständigen Daten, die dem Patienten selbst
gehören und nicht einem einzelnen Besuch. Dokumente hängen ab Sprint 2 an
dieser Tabelle, liegen aber in MongoDB (ADR-0002) und tauchen deshalb hier
nicht als Beziehung auf.
"""

from datetime import UTC, date, datetime
from enum import StrEnum

from sqlalchemy import DateTime, String
from sqlmodel import Field, SQLModel


class InsuranceType(StrEnum):
    """Versicherungsart. Wie die Rolle als String gespeichert, siehe ADR-0005."""

    STATUTORY = "statutory"  # gesetzlich
    PRIVATE = "private"  # privat


class Patient(SQLModel, table=True):
    """Eine in der Praxis behandelte Person."""

    __tablename__ = "patients"

    id: int | None = Field(default=None, primary_key=True)

    # Name und Geburtsdatum sind die einzigen Pflichtangaben. Alles andere kann
    # beim Anlegen am Empfang fehlen und später nachgetragen werden — ein
    # Patient ohne Telefonnummer ist ein gültiger Patient.
    first_name: str = Field(index=True)
    last_name: str = Field(index=True)
    date_of_birth: date

    email: str | None = Field(default=None)
    phone: str | None = Field(default=None)

    street: str | None = Field(default=None)
    postal_code: str | None = Field(default=None)
    city: str | None = Field(default=None)

    insurance_provider: str | None = Field(default=None)
    # Eindeutig, aber optional: Postgres lässt in einem Unique-Index beliebig
    # viele NULL-Werte zu. Mehrere Patienten ohne Nummer sind also erlaubt,
    # zwei Patienten mit derselben Nummer nicht.
    insurance_number: str | None = Field(default=None, unique=True, index=True)
    insurance_type: InsuranceType | None = Field(default=None, sa_type=String)

    notes: str | None = Field(default=None)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=DateTime(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=DateTime(timezone=True),
        # Von der Datenbankschicht gesetzt, damit kein Endpunkt es vergessen kann.
        sa_column_kwargs={"onupdate": lambda: datetime.now(UTC)},
    )
