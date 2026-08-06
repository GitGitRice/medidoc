"""Die Dokumenten-Logik.

Bewusst ohne FastAPI: keine `HTTPException`, keine Statuscodes. Diese Datei
weiß nicht, dass es HTTP gibt; der Router übersetzt (siehe backend/README.md).

Die eine Stelle, an der es hier heikel wird, ist das Anlegen: Es berührt zwei
Speicher — die Datei auf der Platte und die Metadaten in MongoDB. Geht der
zweite Schritt schief, muss der erste zurückgenommen werden, sonst sammeln sich
Dateien an, zu denen es kein Dokument gibt.
"""

import logging
from datetime import UTC, datetime
from typing import Any, BinaryIO
from uuid import uuid4

from app.core.config import settings
from app.modules.documents.schemas import DocumentMetadata, DocumentPublic
from app.modules.documents.storage import get_storage
from app.modules.documents.store import get_store

log = logging.getLogger(__name__)

# Wie bei den Patienten gedeckelt, damit ein versehentliches `limit=100000`
# die Liste nicht lahmlegt.
MAX_LIMIT = 100
DEFAULT_LIMIT = 100


def create(
    patient_id: int,
    metadata: DocumentMetadata,
    quelle: BinaryIO,
    filename: str | None,
    content_type: str | None,
    uploaded_by: int | None = None,
) -> DocumentPublic:
    """Speichert Datei und Angaben. Wirft `FileTooLarge` oder `EmptyFile`."""
    document_id = uuid4().hex
    storage = get_storage()

    gespeichert = storage.save(
        quelle,
        patient_id=patient_id,
        document_id=document_id,
        filename=filename,
        limit_bytes=settings.max_upload_bytes,
    )

    dokument: dict[str, Any] = {
        "_id": document_id,
        "patient_id": patient_id,
        "title": metadata.title,
        "description": metadata.description,
        "tags": metadata.tags,
        "source": metadata.source,
        "created_at": datetime.now(UTC),
        # Der Name des Aufrufers — als Angabe, nie als Pfad (siehe storage.py).
        "filename": filename or f"{document_id}.bin",
        "content_type": content_type,
        "size_bytes": gespeichert.size_bytes,
        "sha256": gespeichert.sha256,
        "stored_as": gespeichert.relative_path,
        "uploaded_by": uploaded_by,
    }

    try:
        get_store().insert(dokument)
    except Exception:
        # Ohne das bliebe eine Datei liegen, zu der es kein Dokument gibt —
        # unsichtbar, unlöschbar über die API, und sie belegt den Platz.
        storage.delete(gespeichert.relative_path)
        log.warning(
            "documents: Metadaten nicht geschrieben, Datei zurückgenommen",
            extra={"patient_id": patient_id},
        )
        raise

    return to_public(dokument)


def search(
    patient_id: int,
    q: str | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> tuple[list[DocumentPublic], int]:
    """Die Dokumente eines Patienten, neueste zuerst."""
    limit = max(1, min(limit, MAX_LIMIT))
    offset = max(0, offset)

    treffer, gesamt = get_store().search(patient_id, q, limit, offset)
    return [to_public(d) for d in treffer], gesamt


def get(patient_id: int, document_id: str) -> DocumentPublic | None:
    """Ein Dokument, sofern es zu diesem Patienten gehört."""
    dokument = get_store().get(patient_id, document_id)
    return to_public(dokument) if dokument else None


def delete(patient_id: int, document_id: str) -> bool:
    """Entfernt Angaben und Datei. `False`, wenn es das Dokument nicht gab.

    Erst die Metadaten, dann die Datei: In der umgekehrten Reihenfolge bliebe
    bei einem Abbruch dazwischen ein Dokument stehen, dessen Datei fehlt — und
    das sieht in der Liste aus wie ein heiles.
    """
    dokument = get_store().get(patient_id, document_id)
    if dokument is None:
        return False

    get_store().delete(patient_id, document_id)
    get_storage().delete(dokument["stored_as"])
    return True


def to_public(dokument: dict[str, Any]) -> DocumentPublic:
    """Aus dem gespeicherten Dokument wird die Form für die API.

    `sha256`, `stored_as` und `uploaded_by` bleiben drinnen: Der Speicherort
    geht niemanden von außen etwas an, und die Prüfsumme beantwortet keine
    Frage, die im Frontend gestellt wird.
    """
    return DocumentPublic(
        id=dokument["_id"],
        patient_id=dokument["patient_id"],
        title=dokument["title"],
        description=dokument.get("description"),
        tags=dokument.get("tags", []),
        source=dokument.get("source"),
        filename=dokument["filename"],
        content_type=dokument.get("content_type"),
        size_bytes=dokument["size_bytes"],
        created_at=dokument["created_at"],
    )
