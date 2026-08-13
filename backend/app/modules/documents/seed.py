"""Testdokumente aus `backend/testdata/documents.json`.

Frei erfunden, wie die Testpatienten daneben — im ganzen Projekt werden
ausschließlich Testdaten verwendet.

Der Seed füllt eine Akte, mit der sich das Frontend ansehen lässt: alle vier
üblichen Dokumenttypen (`befund`, `arztbrief`, `laborwert`, `sonstiges`, siehe
docs/documents-api.md), Dokumente **mit** und **ohne** Anhang, eines nur mit
Pflichtangaben, und Patienten, die gar keine Dokumente haben — der Leerzustand
der Liste ist genauso ein Fall wie eine volle Akte.

Drei Dinge sind hier anders als beim Patienten-Seed:

**Der Patient steht als Versichertennummer in der Datei, nicht als `id`.** Die
`id` vergibt Postgres; sie hängt davon ab, was vorher schon in der Tabelle
stand. Die Nummer gehört dagegen zum Testdatensatz und bleibt dieselbe. Wer mit
`--patients 3` nur die ersten Patienten anlegt, bekommt die übrigen Dokumente
übersprungen statt an falschen Patienten hängend.

**Die Dokumente haben feste Kennungen** (`5eed…`, gut erkennbar gegenüber den
sonst zufälligen). Nur damit ist der Seed mehrfach ausführbar, ohne die Akte
jedes Mal zu verdoppeln — ein zweiter Lauf erkennt sie wieder und überspringt
sie.

**Der Anhang ist ein Platzhalter.** In der Datei steht, wie die Datei hieß und
was der Browser gemeldet hätte; die Bytes selbst schreibt dieser Seed als
kurzen Text. Die API liefert Anhänge (noch) nicht aus — es gibt keinen
Download-Endpunkt (docs/documents-api.md, Offene Punkte) —, ausgeliefert werden
nur Name, Typ und Größe. Die Größe ist damit echt: die des Platzhalters.
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
class SeedDocument:
    """Ein Testdokument, geprüft und fertig zum Anlegen."""

    id: str
    insurance_number: str
    metadata: DocumentMetadata
    created_at: datetime
    filename: str | None
    content_type: str | None


def load_documents() -> list[SeedDocument]:
    """Liest die Datei und prüft jeden Datensatz.

    Wie bei den Patienten laufen die Testdaten durch dieselbe Prüfung wie ein
    echter `POST /docs/{patient_id}` — `DocumentMetadata` trimmt den
    Dokumenttyp, zerlegt die Tags und weist zu große `fields` ab. Ein kaputter
    Datensatz fällt damit beim Seed auf und nicht erst in der Oberfläche.
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

    patient_ids = _patient_ids_by_insurance_number(session)
    storage = get_storage()

    created = 0
    skipped = 0
    without_patient = 0

    for document in load_documents():
        patient_id = patient_ids.get(document.insurance_number)
        if patient_id is None:
            without_patient += 1
            continue

        if store.get(patient_id, document.id) is not None:
            skipped += 1
            continue

        attachment = None
        if document.filename is not None:
            placeholder = _placeholder(document)
            stored = storage.save(
                BytesIO(placeholder),
                patient_id=patient_id,
                document_id=document.id,
                filename=document.filename,
                limit_bytes=settings.max_upload_bytes,
            )
            attachment = {
                "filename": document.filename,
                "content_type": document.content_type,
                "size_bytes": stored.size_bytes,
                "stored_as": stored.relative_path,
            }

        # Von Hand zusammengesetzt und nicht über `service.create`: Der Seed
        # braucht die feste Kennung und das feste Datum aus der Datei, beides
        # vergibt `create` selbst. Bricht der Lauf zwischen Datei und Eintrag
        # ab, bleibt ein Anhang ohne Dokument liegen — der nächste Lauf legt
        # ihn unter derselben Kennung wieder an und überschreibt ihn damit.
        store.insert(
            {
                "_id": document.id,
                "patient_id": patient_id,
                "document_type": document.metadata.document_type,
                "title": document.metadata.title,
                "description": document.metadata.description,
                "tags": document.metadata.tags,
                "source": document.metadata.source,
                "fields": document.metadata.fields,
                "attachment": attachment,
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


def _to_seed_document(record: dict[str, Any]) -> SeedDocument:
    """Ein Datensatz aus der Datei wird zu einem geprüften Testdokument."""
    attachment = record.get("attachment") or {}

    return SeedDocument(
        id=record["id"],
        insurance_number=record["patient"],
        metadata=DocumentMetadata(
            document_type=record["document_type"],
            title=record["title"],
            description=record.get("description"),
            # Kommagetrennt wie im Formular, damit die Testdaten denselben Weg
            # nehmen wie eine echte Eingabe.
            tags=parse_tags(record.get("tags")),
            source=record.get("source"),
            fields=record.get("fields"),
        ),
        created_at=datetime.fromisoformat(record["created_at"]),
        filename=attachment.get("filename"),
        content_type=attachment.get("content_type"),
    )


def _patient_ids_by_insurance_number(session: Session) -> dict[str, int]:
    """Von der Versichertennummer auf die `id` — die Brücke in die Testdaten."""
    return {
        patient.insurance_number: patient.id
        for patient in session.exec(select(Patient)).all()
        if patient.insurance_number and patient.id is not None
    }


def _placeholder(document: SeedDocument) -> bytes:
    """Die Bytes eines Anhangs aus den Testdaten.

    Kein echter Scan, sondern ein kurzer Text, der sagt, was er ist — wer die
    Datei im Volume findet, soll nicht rätseln müssen. Er darf nicht leer sein:
    Ein Anhang mit null Bytes ist ein Versehen und wird abgelehnt
    (`storage.EmptyFile`).
    """
    return (
        "Platzhalter für einen Anhang aus den Testdaten von MediDoc.\n"
        f"Dokument: {document.metadata.title}\n"
        f"Dateiname laut Testdaten: {document.filename}\n"
    ).encode("utf-8")
