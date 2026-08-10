"""Testdokumente aus `backend/testdata/documents.json`.

Frei erfunden, wie die Testpatienten daneben — im ganzen Projekt werden
ausschließlich Testdaten verwendet.

Der Seed füllt eine Akte, mit der sich das Frontend ansehen lässt: alle vier
üblichen Dokumenttypen (`befund`, `arztbrief`, `laborwert`, `sonstiges`, siehe
docs/documents-api.md), Dokumente **mit einem, mit mehreren und ohne** Anhang,
und Patienten, die gar keine Dokumente haben — der Leerzustand der Liste ist
genauso ein Fall wie eine volle Akte.

Drei Dinge sind hier anders als beim Patienten-Seed:

**Der Patient steht als `patient_id` in der Datei.** Sie muss der `id` in
Postgres entsprechen. Das tut sie, weil die Patienten in der Reihenfolge von
`patients.json` angelegt werden und Postgres die Schlüssel fortlaufend ab 1
vergibt — der erste Datensatz wird `1`, der zweite `2`. Das gilt nur für eine
**leere** Tabelle: Wer vorher von Hand Patienten angelegt hat, bekommt andere
Kennungen, und dann hängen die Dokumente an den falschen Leuten. Ein Lauf gegen
`docker compose down -v` ist der Normalfall und stimmt immer.

**Die Dokumente haben feste Kennungen** (`5eed…`, gut erkennbar gegenüber den
sonst zufälligen). Nur damit ist der Seed mehrfach ausführbar, ohne die Akte
jedes Mal zu verdoppeln — ein zweiter Lauf erkennt sie wieder und überspringt
sie. Die Anhänge bekommen ihre Kennung dagegen aus der Position: Datei eins des
Dokuments heißt `…-1`, Datei zwei `…-2`.

**Die Anhänge sind Platzhalter.** In der Datei steht, wie die Datei hieß und
was der Browser gemeldet hätte; die Bytes selbst schreibt dieser Seed als
kurzen Text. Die Größe ist damit echt: die des Platzhalters. Abrufbar sind sie
wie alle anderen, über
`GET /patients/{patient_id}/documents/{document_id}/attachments/{id}`.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlmodel import Session, select

from app.core.config import settings
from app.modules.documents.schemas import DocumentMetadata, parse_tags
from app.modules.documents.storage import get_storage
from app.modules.documents.store import get_store
from app.modules.patients.models import Patient

# app/modules/documents/seed.py -> documents -> modules -> app -> backend
TESTDATA = Path(__file__).resolve().parents[3] / "testdata" / "documents.json"


@dataclass(frozen=True)
class SeedAttachment:
    """Ein Anhang aus den Testdaten."""

    filename: str
    content_type: str | None
    source: str | None


@dataclass(frozen=True)
class SeedDocument:
    """Ein Testdokument, geprüft und fertig zum Anlegen."""

    id: str
    patient_id: int
    metadata: DocumentMetadata
    created_at: datetime
    attachments: list[SeedAttachment]


def load_documents() -> list[SeedDocument]:
    """Liest die Datei und prüft jeden Datensatz.

    Wie bei den Patienten laufen die Testdaten durch dieselbe Prüfung wie ein
    echter `POST /patients/{patient_id}/documents` — `DocumentMetadata` trimmt
    den Dokumenttyp und zerlegt die Tags. Ein kaputter Datensatz fällt damit
    beim Seed auf und nicht erst in der Oberfläche.
    """
    raw = json.loads(TESTDATA.read_text(encoding="utf-8"))

    documents = []
    for position, record in enumerate(raw, start=1):
        try:
            documents.append(_to_seed_document(record))
        except (ValidationError, KeyError, ValueError) as error:
            raise ValueError(
                f"{TESTDATA.name}: Datensatz {position} ist ungültig — {error}"
            ) from error
    return documents


def seed_documents(session: Session) -> None:
    """Legt die Testdokumente an. Vorhandene bleiben unangetastet.

    Braucht die Patienten aus Postgres — die Dokumente hängen an deren `id` —
    und MongoDB für die Angaben. Fehlt `MONGO_URL`, gibt es keinen
    Dokumentenspeicher (ADR-0002); dann wird der Rest des Seeds davon nicht
    aufgehalten, aber es steht in der Ausgabe.
    """
    try:
        store = get_store()
    except RuntimeError as missing_mongo:
        print(f"documents übersprungen: {missing_mongo}")
        return

    known_patients = _existing_patient_ids(session)
    storage = get_storage()

    created = 0
    skipped = 0
    without_patient = 0

    for document in load_documents():
        # Wer mit `--patients 3` nur die ersten Patienten anlegt, bekommt die
        # übrigen Dokumente übersprungen statt an einer Kennung hängend, die es
        # nicht gibt.
        if document.patient_id not in known_patients:
            without_patient += 1
            continue

        if store.get(document.patient_id, document.id) is not None:
            skipped += 1
            continue

        attachments = [
            _write_attachment(storage, document, attachment, position)
            for position, attachment in enumerate(document.attachments, start=1)
        ]

        # Von Hand zusammengesetzt und nicht über `service.create`: Der Seed
        # braucht die feste Kennung und das feste Datum aus der Datei, beides
        # vergibt `create` selbst. Bricht der Lauf zwischen Datei und Eintrag
        # ab, bleiben Anhänge ohne Dokument liegen — der nächste Lauf legt sie
        # unter derselben Kennung wieder an und überschreibt sie damit.
        store.insert(
            {
                "_id": document.id,
                "patient_id": document.patient_id,
                "document_type": document.metadata.document_type,
                "title": document.metadata.title,
                "description": document.metadata.description,
                "tags": document.metadata.tags,
                "attachments": attachments,
                "created_at": document.created_at,
                # Kein Benutzer hat das angelegt, sondern der Seed.
                "created_by": None,
            }
        )
        created += 1

    print(
        f"documents angelegt: {created}, schon vorhanden: {skipped}"
        + (f", ohne Patienten: {without_patient}" if without_patient else "")
    )


def _write_attachment(
    storage: Any, document: SeedDocument, attachment: SeedAttachment, position: int
) -> dict[str, Any]:
    """Schreibt den Platzhalter und gibt die Angaben zum Anhang zurück."""
    attachment_id = f"{document.id}-{position}"

    stored = storage.save(
        BytesIO(_placeholder(document, attachment)),
        patient_id=document.patient_id,
        document_id=document.id,
        attachment_id=attachment_id,
        filename=attachment.filename,
        limit_bytes=settings.max_upload_bytes,
    )

    return {
        "id": attachment_id,
        "filename": attachment.filename,
        "content_type": attachment.content_type,
        "size_bytes": stored.size_bytes,
        "source": attachment.source,
        "stored_as": stored.relative_path,
    }


def _to_seed_document(record: dict[str, Any]) -> SeedDocument:
    """Ein Datensatz aus der Datei wird zu einem geprüften Testdokument."""
    return SeedDocument(
        id=record["id"],
        patient_id=int(record["patient_id"]),
        metadata=DocumentMetadata(
            document_type=record["document_type"],
            title=record["title"],
            description=record.get("description"),
            # Kommagetrennt wie im Formular, damit die Testdaten denselben Weg
            # nehmen wie eine echte Eingabe.
            tags=parse_tags(record.get("tags")),
        ),
        created_at=datetime.fromisoformat(record["created_at"]),
        attachments=[
            SeedAttachment(
                filename=entry["filename"],
                content_type=entry.get("content_type"),
                source=entry.get("source"),
            )
            for entry in record.get("attachments") or []
        ],
    )


def _existing_patient_ids(session: Session) -> set[int]:
    """Welche Patienten es wirklich gibt — die Brücke in die Testdaten."""
    return {
        patient.id
        for patient in session.exec(select(Patient)).all()
        if patient.id is not None
    }


def _placeholder(document: SeedDocument, attachment: SeedAttachment) -> bytes:
    """Die Bytes eines Anhangs aus den Testdaten.

    Kein echter Scan, sondern ein kurzer Text, der sagt, was er ist — wer die
    Datei im Volume findet, soll nicht rätseln müssen. Er darf nicht leer sein:
    Ein Anhang mit null Bytes ist ein Versehen und wird abgelehnt
    (`storage.EmptyFile`).
    """
    return (
        "Platzhalter für einen Anhang aus den Testdaten von MediDoc.\n"
        f"Dokument: {document.metadata.title}\n"
        f"Dateiname laut Testdaten: {attachment.filename}\n"
        f"Herkunft laut Testdaten: {attachment.source or 'nicht angegeben'}\n"
    ).encode("utf-8")
