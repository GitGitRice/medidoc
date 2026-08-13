"""Was von einem Dokument über die API geht.

Ein **Dokument** ist ein Eintrag in der Akte eines Patienten. Es besteht aus
Angaben, deren Felder vom **Dokumenttyp** abhängen, und **optional** aus einem
**Anhang** ([CONTEXT.md](../../../../CONTEXT.md)). Ein Dokument ohne Anhang ist
gültig — ein Laborwert braucht keinen Scan.

Die Angaben zerfallen in zwei Gruppen:

- **Für jeden Typ gleich** — `title`, `description`, `tags`, `source`. Sie
  machen ein Dokument in der Liste auffindbar, unabhängig davon, was es ist.
- **Vom Typ abhängig** — `fields`, ein freier Satz Schlüssel/Wert. Ein `befund`
  trägt hier andere Angaben als ein `laborwert`, und ein neuer Dokumenttyp
  kommt dazu, ohne dass hier eine Zeile geändert wird. Genau das ist die
  Heterogenität, mit der ADR-0002 die zweite Datenbank begründet.

`tags` kommt beim Anlegen als **kommagetrennter Text** herein (`"mrt, radiologie"`)
und geht als **Liste** wieder hinaus (`["mrt", "radiologie"]`). Eine Liste ist die
Form, in der JSON so etwas ausdrückt; das Frontend muss sie nicht zerlegen, und
ein Tag mit Leerzeichen bleibt heil.
"""

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator

# Ein Tag, das länger ist als das, ist keine Schlagwortvergabe mehr.
MAX_TAG_LENGTH = 40
MAX_TAGS = 20

# Grenzen für die typabhängigen Angaben. Sie sind bewusst weit — sie sollen
# einen Unfall abfangen, nicht eine Fachlichkeit vorschreiben, die wir noch
# nicht kennen.
MAX_FIELDS = 50
MAX_FIELD_KEY_LENGTH = 60
MAX_FIELD_VALUE_LENGTH = 500

# Was in einer typabhängigen Angabe stehen darf: ein einzelner Wert, kein Baum.
# Ohne diese Grenze liesse sich ein ganzes verschachteltes Dokument in `fields`
# ablegen, und niemand könnte die Liste noch anzeigen.
#
# `bool` steht **vor** `int`: In Python ist `True` ein `int`, und in der
# umgekehrten Reihenfolge würde aus `"befundet": true` eine `1`. Das liest
# niemand mehr als „ja". Ein Test wacht darüber.
FieldValue = bool | int | float | str


def parse_tags(raw: str | None) -> list[str]:
    """`"MRT, radiologie ,, mrt"` wird zu `["mrt", "radiologie"]`.

    Kleingeschrieben und ohne Dubletten, damit `MRT` und `mrt` beim Filtern
    nicht zwei verschiedene Schlagworte sind. Die Reihenfolge der ersten
    Nennung bleibt erhalten — `dict.fromkeys` statt `set`, sonst wechselte die
    Reihenfolge bei jedem Aufruf und die Liste im Frontend flackerte.
    """
    if not raw:
        return []

    cleaned = []
    for part in raw.split(","):
        tag = part.strip().lower()
        if tag:
            cleaned.append(tag[:MAX_TAG_LENGTH])

    return list(dict.fromkeys(cleaned))[:MAX_TAGS]


def parse_fields(value: Any) -> dict[str, Any]:
    """Nimmt die typabhängigen Angaben als JSON-Objekt entgegen.

    Beim Anlegen reist `fields` als Text im Formular (`{"befund": "…"}`), weil
    ein Multipart-Formular keine verschachtelten Werte kennt; beim Ändern kommt
    es als echtes JSON-Objekt. Beide Wege landen hier, damit für dieselbe
    Eingabe dieselbe Regel gilt.

    Steht als Funktion neben den Models und nicht als Methode darin: Ein
    Validator ist nach dem Dekorieren nicht mehr ohne Weiteres aufrufbar, und
    zwei Models brauchen dieselbe Prüfung.
    """
    if value is None or value == "":
        return {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            raise ValueError("muss ein JSON-Objekt sein") from None
    if not isinstance(value, dict):
        raise ValueError("muss ein JSON-Objekt sein")

    if len(value) > MAX_FIELDS:
        raise ValueError(f"höchstens {MAX_FIELDS} Angaben")

    # Zu lang wird **abgelehnt**, nicht abgeschnitten. Ein stilles Kürzen
    # gäbe ein `201` auf einen Laborwert zurück, in dem hinten etwas fehlt —
    # und niemand sähe es, weil die Antwort den gekürzten Wert genauso
    # ausliefert wie einen ganzen. In einer Akte ist ein abgeschnittener
    # Wert schlimmer als ein abgelehnter. Die Doku sagt an dieser Stelle
    # ohnehin `422` (docs/documents-api.md).
    cleaned: dict[str, Any] = {}
    for key, entry in value.items():
        name = str(key).strip()
        if not name:
            raise ValueError("ein Schlüssel darf nicht leer sein")
        if len(name) > MAX_FIELD_KEY_LENGTH:
            raise ValueError(
                f"„{name[:MAX_FIELD_KEY_LENGTH]}…“ ist länger als "
                f"{MAX_FIELD_KEY_LENGTH} Zeichen"
            )
        if isinstance(entry, (bool, int, float)):
            cleaned[name] = entry
        elif isinstance(entry, str):
            text = entry.strip()
            if len(text) > MAX_FIELD_VALUE_LENGTH:
                raise ValueError(
                    f"der Wert von „{name}“ ist länger als "
                    f"{MAX_FIELD_VALUE_LENGTH} Zeichen"
                )
            cleaned[name] = text
        else:
            raise ValueError(
                f"„{name}“ muss ein einzelner Wert sein, keine Liste und kein Objekt"
            )

    return cleaned


class Attachment(BaseModel):
    """Der Anhang eines Dokuments — die angehängte Datei.

    Eigenes Model und kein Satz einzelner Felder am Dokument: So drückt die
    Antwort aus, was CONTEXT.md sagt — **höchstens einer, und keiner ist
    gültig**. Als drei nullbare Felder nebeneinander liesse sich nicht
    ausdrücken, dass sie nur gemeinsam vorkommen.

    `stored_as` steht hier bewusst **nicht**: Wo der Anhang liegt, geht von
    außen niemanden etwas an.
    """

    filename: str | None = None
    content_type: str | None = None
    size_bytes: int


class DocumentPublic(BaseModel):
    """Ein Dokument, wie die API es ausliefert."""

    id: str
    patient_id: int

    document_type: str
    title: str
    description: str | None = None
    tags: list[str] = []
    source: str | None = None

    # Die typabhängigen Angaben. Leer, solange der Typ keine verlangt.
    fields: dict[str, FieldValue] = {}

    # `None`, wenn das Dokument keinen Anhang hat.
    attachment: Attachment | None = None

    created_at: datetime
    # `None`, solange das Dokument nie geändert wurde. Bewusst nicht mit
    # `created_at` vorbelegt: „nie geändert" und „heute angelegt und geändert"
    # sind zwei verschiedene Aussagen, und in einer Akte zählt der Unterschied.
    updated_at: datetime | None = None


class DocumentPage(BaseModel):
    """Ein Ausschnitt der Dokumentenliste plus die Gesamtzahl.

    Dieselbe Form wie bei den Patienten: `total` ist die Trefferzahl **ohne**
    `limit`/`offset`, damit das Frontend daraus die Seitenzahl bildet.
    """

    items: list[DocumentPublic]
    total: int
    limit: int
    offset: int


class DocumentMetadata(BaseModel):
    """Die Angaben, die beim Anlegen mitkommen — ohne den Anhang.

    Kein Request-Body-Model: Beim Anlegen reist alles als Formularfelder neben
    dem Anhang. Diese Klasse hält die Prüfung an einer Stelle, statt sie in die
    Signatur des Endpunkts zu streuen.
    """

    document_type: str
    title: str
    description: str | None = None
    tags: list[str] = []
    source: str | None = None
    fields: dict[str, FieldValue] = {}

    @field_validator("document_type")
    @classmethod
    def _normalize_document_type(cls, value: str) -> str:
        """Der Dokumenttyp wird getrimmt und kleingeschrieben.

        Wie bei den Tags: Ohne das wären `Befund` und `befund` zwei Typen, und
        eine Liste „alle Befunde" fände nur die Hälfte. Geprüft wird **nicht**
        gegen eine feste Liste — CONTEXT.md verlangt ausdrücklich, dass neue
        Dokumenttypen ohne Schemaänderung möglich sind. Welche üblich sind,
        steht in docs/documents-api.md, nicht im Code.
        """
        cleaned = value.strip().lower()
        if not cleaned:
            raise ValueError("darf nicht leer sein")
        return cleaned

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("darf nicht leer sein")
        return cleaned

    @field_validator("description", "source")
    @classmethod
    def _blank_becomes_none(cls, value: str | None) -> str | None:
        """`""` und `"   "` bedeuten dasselbe wie „nicht angegeben".

        Ohne das käme aus einem leeren Formularfeld ein leerer String statt
        `null`, und das Frontend müsste beides unterscheiden.
        """
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("fields", mode="before")
    @classmethod
    def _parse_fields(cls, value: Any) -> dict[str, Any]:
        return parse_fields(value)


class DocumentUpdate(BaseModel):
    """Der Rumpf von `PATCH` — alles optional.

    **JSON, nicht multipart.** Beim Anlegen reist ein Anhang mit, deshalb ist
    das ein Formular; hier ändern sich nur die Angaben, und dafür ist JSON die
    natürliche Form. Nebeneffekt: FastAPI prüft den Rumpf selbst, das `422`
    entsteht ohne Zutun im gewohnten Format.

    Weggelassene Felder bleiben unverändert. Das Formular im Frontend kann
    einzelne Felder schicken, statt das ganze Dokument zurückzuspielen.

    **Nicht änderbar sind `patient_id` und der Anhang.** Ein Dokument einem
    anderen Patienten zuzuordnen ist keine Korrektur, sondern eine Verlagerung —
    dafür gäbe es Löschen und neu Anlegen. Und ein Anhang reist nicht durch
    JSON.
    """

    document_type: str | None = None
    title: str | None = None
    description: str | None = None
    source: str | None = None

    # Kommagetrennt wie beim Anlegen, damit dieselbe Eingabe denselben Weg
    # nimmt. `""` leert die Schlagworte.
    tags: str | None = None

    # Ersetzt die typabhängigen Angaben **vollständig**, es wird nicht
    # zusammengeführt. Sonst liesse sich ein einmal gesetzter Schlüssel nie
    # wieder entfernen.
    fields: dict[str, FieldValue] | None = None

    @field_validator("document_type")
    @classmethod
    def _document_type_not_blank(cls, value: str | None) -> str:
        """Wie beim Anlegen — und `null` ist hier kein gültiger Wert.

        `document_type` und `title` sind Pflichtangaben des Dokuments. Sie
        dürfen weggelassen, aber nicht geleert werden; sonst entstünde über
        `PATCH` ein Dokument, das über `POST` nie hätte angelegt werden können.
        """
        if value is None:
            raise ValueError("darf nicht auf null gesetzt werden")
        cleaned = value.strip().lower()
        if not cleaned:
            raise ValueError("darf nicht leer sein")
        return cleaned

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("darf nicht auf null gesetzt werden")
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("darf nicht leer sein")
        return cleaned

    @field_validator("description", "source")
    @classmethod
    def _blank_becomes_none(cls, value: str | None) -> str | None:
        """`""` leert das Feld — hier ist das eine gültige Absicht."""
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("fields", mode="before")
    @classmethod
    def _parse_fields(cls, value: Any) -> Any:
        """Dieselbe Prüfung wie beim Anlegen.

        `None` heißt hier „nicht mitgeschickt" und bleibt `None` — sonst würde
        ein `PATCH` ohne `fields` die vorhandenen Angaben leeren.
        """
        if value is None:
            return None
        return parse_fields(value)
