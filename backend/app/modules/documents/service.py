"""Die Dokumenten-Logik.

Bewusst ohne FastAPI: keine `HTTPException`, keine Statuscodes. Diese Datei
weiß nicht, dass es HTTP gibt; der Router übersetzt (siehe backend/README.md).

Die eine Stelle, an der es hier heikel wird, ist das Anlegen **mit Anhang**: Es
berührt zwei Speicher — den Anhang auf der Platte und die Angaben in MongoDB.
Geht der zweite Schritt schief, muss der erste zurückgenommen werden, sonst
sammeln sich Anhänge an, zu denen es kein Dokument gibt.

Ein Dokument **ohne** Anhang fasst die Platte gar nicht erst an.
"""

import logging
from datetime import UTC, datetime
from typing import Any, BinaryIO
from uuid import uuid4

from app.core.config import settings
from app.modules.documents.schemas import (
    Attachment,
    DocumentMetadata,
    DocumentPublic,
    DocumentUpdate,
    parse_tags,
)
from app.modules.documents.storage import get_storage
from app.modules.documents.store import get_store

log = logging.getLogger(__name__)

# Wie bei den Patienten gedeckelt, damit ein versehentliches `limit=100000`
# die Liste nicht lahmlegt. Anders als dort ist das gleichzeitig der Standard:
# Ein Patient hat ein paar Dutzend Dokumente, nicht ein paar Tausend — die
# Liste zeigt sie ohne Blättern, und der Deckel greift nur im Ausreißerfall.
MAX_LIMIT = 100


def _now() -> datetime:
    """Der aktuelle Zeitpunkt, auf Millisekunden gekürzt.

    BSON speichert einen Zeitpunkt als Millisekunden seit Epoch — Mikrosekunden
    gehen beim Schreiben verloren. Ohne das Kürzen gäbe `POST` einen
    `created_at` mit Mikrosekunden zurück, und jeder spätere Aufruf lieferte für
    dasselbe Dokument einen anderen Wert. Ein Frontend, das den Zeitpunkt aus
    der Anlege-Antwort behält und später vergleicht, fände nie eine
    Übereinstimmung.

    Also lieber von vornherein die Genauigkeit ausliefern, die auch ankommt.
    """
    now = datetime.now(UTC)
    return now.replace(microsecond=(now.microsecond // 1000) * 1000)


def create(
    patient_id: int,
    metadata: DocumentMetadata,
    stream: BinaryIO | None = None,
    filename: str | None = None,
    content_type: str | None = None,
    created_by: int | None = None,
) -> DocumentPublic:
    """Legt ein Dokument an, mit oder ohne Anhang.

    Wirft `FileTooLarge` oder `EmptyFile` — beides nur, wenn ein Anhang dabei
    ist.
    """
    document_id = uuid4().hex

    attachment: dict[str, Any] | None = None
    if stream is not None:
        storage = get_storage()
        stored = storage.save(
            stream,
            patient_id=patient_id,
            document_id=document_id,
            filename=filename,
            limit_bytes=settings.max_upload_bytes,
        )
        attachment = {
            # Der Name des Aufrufers — als Angabe, nie als Pfad (siehe
            # storage.py). Schickt er keinen, bleibt das Feld `None`: Ein hier
            # erfundener Name sähe für das Frontend aus wie ein echter.
            "filename": filename or None,
            "content_type": content_type,
            "size_bytes": stored.size_bytes,
            "stored_as": stored.relative_path,
        }

    document: dict[str, Any] = {
        "_id": document_id,
        "patient_id": patient_id,
        "document_type": metadata.document_type,
        "title": metadata.title,
        "description": metadata.description,
        "tags": metadata.tags,
        "source": metadata.source,
        "fields": metadata.fields,
        "attachment": attachment,
        "created_at": _now(),
        "created_by": created_by,
    }

    try:
        get_store().insert(document)
    except Exception:
        # Ohne das bliebe ein Anhang liegen, zu dem es kein Dokument gibt —
        # unsichtbar, unlöschbar über die API, und er belegt den Platz.
        if attachment is not None:
            get_storage().delete(attachment["stored_as"])
            log.warning(
                "documents: Angaben nicht geschrieben, Anhang zurückgenommen",
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


def update(
    patient_id: int, document_id: str, data: DocumentUpdate
) -> DocumentPublic | None:
    """Ändert die Angaben eines Dokuments. `None`, wenn es das nicht gibt.

    `exclude_unset` ist hier der entscheidende Teil: Ohne das würden alle nicht
    geschickten Felder mit ihrem Vorgabewert `None` überschrieben — ein `PATCH`
    mit einem Feld leerte den Rest des Dokuments.

    Der Anhang wird nicht angefasst. Er reist nicht durch JSON, und ihn
    auszutauschen wäre kein Ändern der Angaben, sondern ein neuer Anhang.
    """
    changes: dict[str, Any] = data.model_dump(exclude_unset=True)

    # Die Schlagworte kommen kommagetrennt herein wie im Formular.
    if "tags" in changes:
        changes["tags"] = parse_tags(changes["tags"])

    # Auch ein `PATCH` ohne ein einziges Feld ist gültig — er ändert dann nur
    # den Zeitstempel. Der gehört trotzdem gesetzt: Die Antwort behauptet
    # sonst, das Dokument sei nie angefasst worden.
    changes["updated_at"] = _now()

    document = get_store().update(patient_id, document_id, changes)
    return to_public(document) if document else None


def delete(patient_id: int, document_id: str) -> bool:
    """Entfernt Angaben und Anhang. `False`, wenn es das Dokument nicht gab.

    Erst die Angaben, dann der Anhang: In der umgekehrten Reihenfolge bliebe
    bei einem Abbruch dazwischen ein Dokument stehen, dessen Anhang fehlt — und
    das sieht in der Liste aus wie ein heiles.
    """
    store = get_store()

    document = store.get(patient_id, document_id)
    if document is None:
        return False

    store.delete(patient_id, document_id)

    attachment = document.get("attachment")
    if attachment is not None:
        get_storage().delete(attachment["stored_as"])
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
    niemanden von außen etwas an.
    """
    attachment = document.get("attachment")

    return DocumentPublic(
        id=document["_id"],
        patient_id=document["patient_id"],
        document_type=document["document_type"],
        title=document["title"],
        description=document.get("description"),
        tags=document.get("tags", []),
        source=document.get("source"),
        fields=document.get("fields") or {},
        attachment=(
            Attachment(
                filename=attachment.get("filename"),
                content_type=attachment.get("content_type"),
                size_bytes=attachment["size_bytes"],
            )
            if attachment is not None
            else None
        ),
        created_at=document["created_at"],
        updated_at=document.get("updated_at"),
    )
