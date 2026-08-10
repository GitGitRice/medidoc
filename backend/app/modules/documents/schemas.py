"""Was von einem Dokument über die API geht.

Ein **Dokument** ist ein Eintrag in der Akte eines Patienten. Es besteht aus
beschreibenden Angaben und aus beliebig vielen **Anhängen**
([CONTEXT.md](../../../../CONTEXT.md)). Ein Dokument ohne Anhang ist gültig —
ein Laborwert braucht keinen Scan.

Alle Dokumente tragen dieselben Angaben — `document_type`, `title`,
`description`, `tags`. **Typabhängige Felder gibt es (noch) nicht**, und das
ist eine Entscheidung, keine Lücke:

> Ein freier Satz Schlüssel/Wert je Dokument klingt nach Flexibilität, führt
> aber ohne eine **Definition je Dokumenttyp** direkt in redundante Daten. Ohne
> Katalog schreibt der eine `hb`, der nächste `Hb` und der dritte
> `haemoglobin` — drei Schlüssel für denselben Wert, und keine Auswertung
> findet sie zusammen. Ein Pflichtfeld lässt sich nicht erzwingen, ein Tippfehler
> nicht bemerken, eine Einheit nicht prüfen.
>
> Typabhängige Felder kommen deshalb erst, wenn **je Dokumenttyp festgelegt
> ist, welche Felder es gibt** — Name, Typ, Einheit, Pflicht ja/nein. Dann
> validiert das Backend gegen diesen Katalog, und das Frontend baut das
> Formular daraus. Bis dahin: keine Felder statt beliebiger Felder. Die
> Begründung steht ausführlich in docs/documents-api.md.

**Mehrere Anhänge sind erlaubt.** Ein Befund aus drei gescannten Seiten ist ein
Dokument mit drei Anhängen und nicht drei Dokumente — die Antwort auf die
offene Frage 4 im Sprint-1-Plan, in CONTEXT.md nachgezogen.

**`source` gehört zum Anhang, nicht zum Dokument.** Die Herkunft beschreibt,
woher *dieses Blatt* kam; ein Dokument kann Anhänge aus verschiedenen Quellen
bündeln — den Scan aus der Radiologie und die Notiz aus der eigenen Praxis.

`tags` kommt beim Anlegen als **kommagetrennter Text** herein (`"mrt, radiologie"`)
und geht als **Liste** wieder hinaus (`["mrt", "radiologie"]`). Eine Liste ist die
Form, in der JSON so etwas ausdrückt; das Frontend muss sie nicht zerlegen, und
ein Tag mit Leerzeichen bleibt heil.
"""

from datetime import datetime

from pydantic import BaseModel, field_validator

# Ein Tag, das länger ist als das, ist keine Schlagwortvergabe mehr.
MAX_TAG_LENGTH = 40
MAX_TAGS = 20

# Wie viele Anhänge ein Dokument tragen darf. Weit genug für einen gescannten
# Arztbrief, eng genug, dass ein Versehen im Formular auffällt.
MAX_ATTACHMENTS = 20


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


class Attachment(BaseModel):
    """Ein Anhang eines Dokuments.

    `stored_as` steht hier bewusst **nicht**: Wo der Anhang liegt, geht von
    außen niemanden etwas an. Stattdessen gibt es `url` — die Adresse, unter
    der die Bytes abzuholen sind.
    """

    id: str

    filename: str | None = None
    content_type: str | None = None
    size_bytes: int

    # Woher dieses Blatt stammt, z. B. "Radiologie Mitte".
    source: str | None = None

    # Zwei fertige Adressen, damit das Frontend keine selbst bauen muss.
    #
    # `url` liefert den Anhang zum **Ansehen**: `<img src={a.url}>` oder ein
    # `<iframe>` mit einem PDF zeigen ihn direkt, weil die Antwort
    # `Content-Disposition: inline` trägt.
    #
    # `download_url` erzwingt den **Speichern**-Dialog (`attachment`) und gibt
    # dem Browser den ursprünglichen Dateinamen mit: `<a href={a.download_url}
    # download>`. Dieselbe Route, nur `?download=true`.
    #
    # Ändert sich der Pfad, ändert er sich an einer Stelle im Backend und
    # nirgends im Frontend.
    url: str
    download_url: str


class DocumentPublic(BaseModel):
    """Ein Dokument, wie die API es ausliefert."""

    id: str
    patient_id: int

    document_type: str
    title: str
    description: str | None = None
    tags: list[str] = []

    # Leer, wenn das Dokument keine Anhänge hat — ein Laborwert braucht keinen
    # Scan. Nie `null`: Eine leere Liste lässt sich im Frontend ohne Fallprüfung
    # durchlaufen.
    attachments: list[Attachment] = []

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
    """Die Angaben, die beim Anlegen mitkommen — ohne die Anhänge.

    Kein Request-Body-Model: Beim Anlegen reist alles als Formularfelder neben
    den Anhängen. Diese Klasse hält die Prüfung an einer Stelle, statt sie in
    die Signatur des Endpunkts zu streuen.
    """

    document_type: str
    title: str
    description: str | None = None
    tags: list[str] = []

    @field_validator("document_type")
    @classmethod
    def _normalize_document_type(cls, value: str) -> str:
        """Der Dokumenttyp wird getrimmt und kleingeschrieben.

        Wie bei den Tags: Ohne das wären `Befund` und `befund` zwei Typen, und
        eine Liste „alle Befunde" fände nur die Hälfte. Geprüft wird **nicht**
        gegen eine feste Liste — neue Dokumenttypen sollen ohne Schemaänderung
        möglich sein. Welche üblich sind, steht in docs/documents-api.md, nicht
        im Code.
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

    @field_validator("description")
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

