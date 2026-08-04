"""Was von einem Patienten über die API geht.

Getrennt vom Model, weil Eingabe, Ausgabe und Tabelle drei verschiedene Formen
haben: Beim Anlegen gibt es keine `id`, beim Bearbeiten ist alles optional, und
die Übersichtstabelle braucht nicht jedes Feld.

Die Form ist der Vertrag mit dem Frontend — Änderungen hier gehören ins Daily.
"""

from datetime import date, datetime

from pydantic import field_validator
from sqlmodel import SQLModel

from app.modules.patients.models import InsuranceType


class PatientBase(SQLModel):
    """Die Felder, die von außen gesetzt werden dürfen.

    `id`, `created_at` und `updated_at` fehlen bewusst: Die vergibt der Server.
    """

    first_name: str
    last_name: str
    date_of_birth: date

    email: str | None = None
    phone: str | None = None

    street: str | None = None
    postal_code: str | None = None
    city: str | None = None

    insurance_provider: str | None = None
    insurance_number: str | None = None
    insurance_type: InsuranceType | None = None

    notes: str | None = None

    @field_validator("first_name", "last_name")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        """Fängt Leerzeichen-Namen ab — `""` und `"   "` sind kein Name."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("darf nicht leer sein")
        return cleaned

    @field_validator("date_of_birth")
    @classmethod
    def _not_in_future(cls, value: date) -> date:
        """Ein Geburtsdatum in der Zukunft ist immer ein Tippfehler."""
        if value > date.today():
            raise ValueError("darf nicht in der Zukunft liegen")
        return value


class PatientCreate(PatientBase):
    """Rumpf von `POST /patients`."""


class PatientUpdate(SQLModel):
    """Rumpf von `PATCH /patients/{id}` — alles optional.

    Weggelassene Felder bleiben unverändert. Das Formular im Frontend kann
    damit einzelne Felder schicken, statt den ganzen Patienten zurückzuspielen.
    """

    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None

    email: str | None = None
    phone: str | None = None

    street: str | None = None
    postal_code: str | None = None
    city: str | None = None

    insurance_provider: str | None = None
    insurance_number: str | None = None
    insurance_type: InsuranceType | None = None

    notes: str | None = None

    # Diese drei Felder sind in der Tabelle NOT NULL. Sie dürfen weggelassen,
    # aber nicht auf null gesetzt werden — sonst schlüge erst die Datenbank zu,
    # mit einem 500 statt einem 422.
    @field_validator("first_name", "last_name")
    @classmethod
    def _not_blank(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("darf nicht auf null gesetzt werden")
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("darf nicht leer sein")
        return cleaned

    @field_validator("date_of_birth")
    @classmethod
    def _valid_date(cls, value: date | None) -> date:
        if value is None:
            raise ValueError("darf nicht auf null gesetzt werden")
        if value > date.today():
            raise ValueError("darf nicht in der Zukunft liegen")
        return value


class PatientPublic(PatientBase):
    """Antwort der Detail-Endpunkte: der vollständige Patient."""

    id: int
    created_at: datetime
    updated_at: datetime


class PatientListItem(SQLModel):
    """Eine Zeile der Patientenübersicht.

    Bewusst schmal — die Tabelle zeigt nur diese Spalten. Wer mehr braucht,
    öffnet den Patienten und bekommt `PatientPublic`.
    """

    id: int
    first_name: str
    last_name: str
    date_of_birth: date
    insurance_number: str | None


class PatientPage(SQLModel):
    """Ein Ausschnitt der Übersicht plus die Gesamtzahl.

    `total` ist die Trefferzahl **ohne** `limit`/`offset` — das Frontend braucht
    sie für die Seitenzahl und für "42 Patienten gefunden".
    """

    items: list[PatientListItem]
    total: int
    limit: int
    offset: int
