"""Die Dokumenten-Logik.

Bewusst ohne FastAPI: keine `HTTPException`, keine Statuscodes. Diese Datei
weiß nicht, dass es HTTP gibt; der Router übersetzt (siehe backend/README.md).

Die eine Stelle, an der es hier heikel wird, ist das Anlegen **mit Anhängen**:
Es berührt zwei Speicher — die Bytes auf der Platte und die Angaben in MongoDB.
Geht der zweite Schritt schief, müssen **alle** schon geschriebenen Anhänge
zurückgenommen werden, sonst sammeln sich Bytes an, zu denen es kein Dokument
gibt.

Ein Dokument **ohne** Anhang fasst die Platte gar nicht erst an.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, BinaryIO
from uuid import uuid4

from app.core.config import settings
from app.modules.documents.schemas import (
    Attachment,
    DocumentMetadata,
    DocumentPublic,
)
from app.modules.documents.storage import get_storage
from app.modules.documents.store import get_store

log = logging.getLogger(__name__)

# Wie bei den Patienten gedeckelt, damit ein versehentliches `limit=100000`
# die Liste nicht lahmlegt. Anders als dort ist das gleichzeitig der Standard:
# Ein Patient hat ein paar Dutzend Dokumente, nicht ein paar Tausend — die
# Liste zeigt sie ohne Blättern, und der Deckel greift nur im Ausreißerfall.
MAX_LIMIT = 100


@dataclass(frozen=True)
class IncomingAttachment:
    """Ein Anhang auf dem Weg herein — Bytes plus die Angaben dazu.

    Hält den Router davon ab, dem Service vier parallele Listen zu übergeben,
    bei denen der dritte Dateiname zur zweiten Herkunft gehören könnte.
    """

    stream: BinaryIO
    filename: str | None = None
    content_type: str | None = None
    source: str | None = None


def attachment_url(
    patient_id: int, document_id: str, attachment_id: str, download: bool = False
) -> str:
    """Die Adresse, unter der ein Anhang abzuholen ist.

    `download=True` hängt den Schalter an, der den Speichern-Dialog auslöst
    statt der Vorschau.

    Steht hier und nicht im Router, damit die Antwort und die Route nicht
    getrennt voneinander wandern können. Ein Test hält beide zusammen.
    """
    url = (
        f"/patients/{patient_id}/documents/{document_id}/attachments/{attachment_id}"
    )
    return f"{url}?download=true" if download else url


def create(
    patient_id: int,
    metadata: DocumentMetadata,
    attachments: list[IncomingAttachment] | None = None,
    created_by: int | None = None,
) -> DocumentPublic:
    """Legt ein Dokument an, mit beliebig vielen Anhängen oder ganz ohne.

    Wirft `FileTooLarge` oder `EmptyFile` — beides nur, wenn Anhänge dabei sind.
    """
    document_id = uuid4().hex
    storage = get_storage()

    stored_attachments: list[dict[str, Any]] = []

    try:
        for incoming in attachments or []:
            attachment_id = uuid4().hex
            stored = storage.save(
                incoming.stream,
                patient_id=patient_id,
                document_id=document_id,
                attachment_id=attachment_id,
                filename=incoming.filename,
                limit_bytes=settings.max_upload_bytes,
            )
            stored_attachments.append(
                {
                    "id": attachment_id,
                    # Der Name des Aufrufers — als Angabe, nie als Pfad (siehe
                    # storage.py). Schickt er keinen, bleibt das Feld `None`:
                    # Ein hier erfundener Name sähe für das Frontend aus wie
                    # ein echter.
                    "filename": incoming.filename or None,
                    "content_type": incoming.content_type,
                    "size_bytes": stored.size_bytes,
                    "source": incoming.source,
                    "stored_as": stored.relative_path,
                }
            )
    except BaseException:
        # Der dritte Anhang ist zu groß? Dann dürfen auch die ersten beiden
        # nicht liegenbleiben — es entsteht ja kein Dokument, das sie hielte.
        storage.delete_document_folder(patient_id, document_id)
        raise

    document: dict[str, Any] = {
        "_id": document_id,
        "patient_id": patient_id,
        "document_type": metadata.document_type,
        "title": metadata.title,
        "description": metadata.description,
        "tags": metadata.tags,
        "attachments": stored_attachments,
        "created_at": datetime.now(UTC),
        "created_by": created_by,
    }

    try:
        get_store().insert(document)
    except Exception:
        # Ohne das blieben Anhänge liegen, zu denen es kein Dokument gibt —
        # unsichtbar, unlöschbar über die API, und sie belegen den Platz.
        storage.delete_document_folder(patient_id, document_id)
        log.warning(
            "documents: Angaben nicht geschrieben, Anhänge zurückgenommen",
            extra={"patient_id": patient_id},
        )
        raise

    return to_public(document)


def search(
    patient_id: int,
    q: str | None = None,
    limit: int = MAX_LIMIT,
    offset: int = 0,
) -> tuple[list[DocumentPublic], int]:
    """Die Dokumente eines Patienten, neueste zuerst."""
    # Der Router prüft `limit` schon über `Query(ge=1, le=MAX_LIMIT)`. Hier
    # steht es trotzdem — wie bei den Patienten —, damit die Logik auch dann
    # hält, wenn sie ohne Router aufgerufen wird.
    limit = max(1, min(limit, MAX_LIMIT))
    offset = max(0, offset)

    matches, total = get_store().search(patient_id, q, limit, offset)
    return [to_public(d) for d in matches], total


def get(patient_id: int, document_id: str) -> DocumentPublic | None:
    """Ein Dokument, sofern es zu diesem Patienten gehört."""
    document = get_store().get(patient_id, document_id)
    return to_public(document) if document else None


@dataclass(frozen=True)
class StoredAttachment:
    """Ein Anhang zum Ausliefern — der Pfad und was in die Antwort gehört."""

    path: Any
    filename: str
    content_type: str


def open_attachment(
    patient_id: int, document_id: str, attachment_id: str
) -> StoredAttachment | None:
    """Findet einen Anhang und sagt, wo seine Bytes liegen.

    `None`, wenn Patient, Dokument oder Anhang nicht zusammenpassen — der
    Router macht daraus ein `404`. Die drei Kennungen werden **alle** geprüft:
    Wer die Kennung eines fremden Anhangs errät, soll ihn nicht über den
    eigenen Patienten abrufen können.
    """
    document = get_store().get(patient_id, document_id)
    if document is None:
        return None

    for attachment in document.get("attachments", []):
        if attachment["id"] != attachment_id:
            continue

        path = get_storage().resolve(attachment["stored_as"])
        if not path.is_file():
            # Die Angaben sagen, es gäbe ihn; auf der Platte liegt nichts.
            # Für den Aufrufer ist das dasselbe wie „gibt es nicht", im Log
            # ist es ein Befund.
            log.error(
                "documents: Anhang fehlt auf der Platte",
                extra={"document_id": document_id, "attachment_id": attachment_id},
            )
            return None

        return StoredAttachment(
            path=path,
            # Beides mit Rückfallwert: Der Browser braucht einen Namen für den
            # Speichern-Dialog und einen Typ, um zu entscheiden, ob er die
            # Datei anzeigt oder herunterlädt.
            filename=attachment.get("filename") or f"{attachment_id}.bin",
            content_type=attachment.get("content_type") or "application/octet-stream",
        )

    return None


def delete(patient_id: int, document_id: str) -> bool:
    """Entfernt Angaben und alle Anhänge. `False`, wenn es das Dokument nicht gab.

    Erst die Angaben, dann die Bytes: In der umgekehrten Reihenfolge bliebe
    bei einem Abbruch dazwischen ein Dokument stehen, dessen Anhänge fehlen —
    und das sieht in der Liste aus wie ein heiles.
    """
    store = get_store()

    if store.get(patient_id, document_id) is None:
        return False

    store.delete(patient_id, document_id)
    get_storage().delete_document_folder(patient_id, document_id)
    return True


def delete_for_patient(patient_id: int) -> int:
    """Räumt alle Dokumente eines Patienten ab. Gibt die Anzahl zurück.

    Wird beim Löschen eines Patienten aufgerufen. Ohne das blieben Angaben
    und Anhänge liegen: über die API nicht mehr erreichbar, weil jeder Endpunkt
    den Patienten voraussetzt, und trotzdem auf der Platte.

    `finally`, nicht nacheinander: Der Patient ist in Postgres schon weg, und
    ohne ihn führt kein Weg mehr zu seinen Anhängen. Scheitert das Entfernen
    der Angaben — etwa weil MongoDB gerade nicht antwortet —, wird die Platte
    **trotzdem** abgeräumt; sonst lägen die Bytes für immer da, ohne dass sie
    noch jemand findet. Der Fehler geht danach weiter nach oben und wird zur
    `500` (siehe docs/documents-api.md).
    """
    try:
        return get_store().delete_for_patient(patient_id)
    finally:
        get_storage().delete_patient_folder(patient_id)


def to_public(document: dict[str, Any]) -> DocumentPublic:
    """Aus dem gespeicherten Dokument wird die Form für die API.

    `stored_as` und `created_by` bleiben drinnen: Der Speicherort geht
    niemanden von außen etwas an. An seine Stelle tritt `url`.
    """
    patient_id = document["patient_id"]
    document_id = document["_id"]

    return DocumentPublic(
        id=document_id,
        patient_id=patient_id,
        document_type=document["document_type"],
        title=document["title"],
        description=document.get("description"),
        tags=document.get("tags", []),
        attachments=[
            Attachment(
                id=attachment["id"],
                filename=attachment.get("filename"),
                content_type=attachment.get("content_type"),
                size_bytes=attachment["size_bytes"],
                source=attachment.get("source"),
                url=attachment_url(patient_id, document_id, attachment["id"]),
                download_url=attachment_url(
                    patient_id, document_id, attachment["id"], download=True
                ),
            )
            for attachment in document.get("attachments") or []
        ],
        created_at=document["created_at"],
    )
