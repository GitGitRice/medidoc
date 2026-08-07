"""Was von einem Dokument über die API geht.

Die Felder sind die aus der Anforderung: `id`, `title`, `description`,
`created_at`, `tags`, `source`. Dazu drei, ohne die eine Dateiliste im Frontend
nicht bedienbar wäre — `filename`, `size_bytes`, `content_type`.

`tags` kommt beim Hochladen als **kommagetrennter Text** herein (`"mrt, radiologie"`)
und geht als **Liste** wieder hinaus (`["mrt", "radiologie"]`). Eine Liste ist die
Form, in der JSON so etwas ausdrückt; das Frontend muss sie nicht zerlegen, und
ein Tag mit Leerzeichen bleibt heil.
"""

from datetime import datetime

from pydantic import BaseModel, field_validator

# Ein Tag, das länger ist als das, ist keine Schlagwortvergabe mehr.
MAX_TAG_LENGTH = 40
MAX_TAGS = 20


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


class DocumentPublic(BaseModel):
    """Ein Dokument, wie die API es ausliefert."""

    id: str
    patient_id: int

    title: str
    description: str | None = None
    tags: list[str] = []
    source: str | None = None

    # Die Datei selbst — ohne diese drei ließe sich die Liste nicht anzeigen.
    filename: str
    content_type: str | None = None
    size_bytes: int

    created_at: datetime


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
    """Die Angaben, die beim Hochladen mitkommen — ohne die Datei.

    Kein Request-Body-Model: Beim Upload reist alles als Formularfelder neben
    der Datei. Diese Klasse hält die Prüfung an einer Stelle, statt sie in die
    Signatur des Endpunkts zu streuen.
    """

    title: str
    description: str | None = None
    tags: list[str] = []
    source: str | None = None

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
