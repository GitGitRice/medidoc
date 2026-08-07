"""Die Angaben zu den Dokumenten — in MongoDB.

Zwei Ausführungen hinter derselben Schnittstelle, wie beim Audit-Trail:
`MongoDocumentStore` für den Betrieb, `MemoryDocumentStore` für die Tests und
für den Start ohne Mongo.

**Anders als beim Audit-Trail werden Fehler hier nicht geschluckt.** Ein
verlorener Protokolleintrag ist ärgerlich; ein Upload, der „ok" meldet und
dessen Dokument danach nirgends auftaucht, ist schlimmer als eine
Fehlermeldung. Was hier schiefgeht, wird zur Antwort.
"""

import re
from typing import Any, Protocol

COLLECTION = "documents"


def _search_filter(patient_id: int, q: str | None) -> dict[str, Any]:
    """Der Filter für Liste und Zählung — für beide derselbe.

    `q` trifft in Titel **oder** Beschreibung, Groß- und Kleinschreibung egal.
    `re.escape` ist hier nicht Kosmetik: Ohne das wäre eine Suche nach `.*` ein
    Ausdruck, der alles findet, und eine nach `(` ein Fehler.
    """
    query: dict[str, Any] = {"patient_id": patient_id}

    if q and q.strip():
        pattern = re.escape(q.strip())
        query["$or"] = [
            {"title": {"$regex": pattern, "$options": "i"}},
            {"description": {"$regex": pattern, "$options": "i"}},
        ]

    return query


class DocumentStore(Protocol):
    def insert(self, document: dict[str, Any]) -> None: ...

    def get(self, patient_id: int, document_id: str) -> dict[str, Any] | None: ...

    def search(
        self, patient_id: int, q: str | None, limit: int, offset: int
    ) -> tuple[list[dict[str, Any]], int]: ...

    def delete(self, patient_id: int, document_id: str) -> bool:
        """`True`, wenn wirklich etwas gelöscht wurde."""

    def delete_for_patient(self, patient_id: int) -> int:
        """Entfernt alle Dokumente eines Patienten, gibt die Anzahl zurück."""


class MemoryDocumentStore:
    """Metadaten im Prozessspeicher. Für Tests und den Betrieb ohne Mongo."""

    def __init__(self) -> None:
        self._documents: list[dict[str, Any]] = []

    def insert(self, document: dict[str, Any]) -> None:
        self._documents.append(dict(document))

    def get(self, patient_id: int, document_id: str) -> dict[str, Any] | None:
        for document in self._documents:
            if document["_id"] == document_id and document["patient_id"] == patient_id:
                return dict(document)
        return None

    def search(
        self, patient_id: int, q: str | None, limit: int, offset: int
    ) -> tuple[list[dict[str, Any]], int]:
        term = (q or "").strip().lower()

        matches = [
            document
            for document in self._documents
            if document["patient_id"] == patient_id
            and (
                not term
                or term in document["title"].lower()
                or term in (document.get("description") or "").lower()
            )
        ]
        # Neueste zuerst, `_id` als Stichentscheid — sonst wechselte die
        # Reihenfolge bei gleichem Zeitstempel und das Blättern zeigte
        # Dokumente doppelt.
        matches.sort(key=lambda d: (d["created_at"], d["_id"]), reverse=True)

        return [dict(d) for d in matches[offset : offset + limit]], len(matches)

    def delete(self, patient_id: int, document_id: str) -> bool:
        before = len(self._documents)
        self._documents = [
            d
            for d in self._documents
            if not (d["_id"] == document_id and d["patient_id"] == patient_id)
        ]
        return len(self._documents) < before

    def delete_for_patient(self, patient_id: int) -> int:
        before = len(self._documents)
        self._documents = [
            d for d in self._documents if d["patient_id"] != patient_id
        ]
        return before - len(self._documents)


class MongoDocumentStore:
    """Metadaten in MongoDB — dauerhaft, durchsuchbar."""

    def __init__(self, url: str, database: str) -> None:
        from pymongo import ASCENDING, DESCENDING, MongoClient

        self._client: Any = MongoClient(
            url,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
        )
        self._collection = self._client[database][COLLECTION]
        self._ascending = ASCENDING
        self._descending = DESCENDING

    def ensure_indexes(self) -> None:
        """Legt die Indizes an. Verträgt Wiederholung.

        Ohne diesen Index läse jede Dokumentenliste die ganze Collection — also
        auch die Dokumente aller anderen Patienten.
        """
        self._collection.create_index(
            [("patient_id", self._ascending), ("created_at", self._descending)],
            name="patient_created",
        )

    def insert(self, document: dict[str, Any]) -> None:
        self._collection.insert_one(dict(document))

    def get(self, patient_id: int, document_id: str) -> dict[str, Any] | None:
        return self._collection.find_one({"_id": document_id, "patient_id": patient_id})

    def search(
        self, patient_id: int, q: str | None, limit: int, offset: int
    ) -> tuple[list[dict[str, Any]], int]:
        query = _search_filter(patient_id, q)

        matches = (
            self._collection.find(query)
            .sort([("created_at", self._descending), ("_id", self._descending)])
            .skip(offset)
            .limit(limit)
        )

        return list(matches), self._collection.count_documents(query)

    def delete(self, patient_id: int, document_id: str) -> bool:
        result = self._collection.delete_one(
            {"_id": document_id, "patient_id": patient_id}
        )
        return result.deleted_count > 0

    def delete_for_patient(self, patient_id: int) -> int:
        return self._collection.delete_many({"patient_id": patient_id}).deleted_count


_store: DocumentStore | None = None


def get_store() -> DocumentStore:
    """Der Dokumentenspeicher dieser Anwendung."""
    global _store
    if _store is None:
        _store = _build_store()
    return _store


def set_store(store: DocumentStore | None) -> None:
    """Setzt den Speicher — für Tests, und um ihn wieder zurückzusetzen."""
    global _store
    _store = store


def _build_store() -> DocumentStore:
    import logging

    from app.core.config import settings

    log = logging.getLogger(__name__)

    if not settings.mongo_url:
        log.info("documents: kein MONGO_URL gesetzt, Metadaten liegen im Speicher")
        return MemoryDocumentStore()

    store = MongoDocumentStore(settings.mongo_url, settings.mongo_db)
    try:
        store.ensure_indexes()
    except Exception:
        # Ein fehlender Index macht die Liste langsam, nicht falsch — das ist
        # kein Grund, die Anwendung nicht zu starten. Schreib- und Lesefehler
        # kommen später sehr wohl durch.
        log.warning("documents: Indizes konnten nicht angelegt werden", exc_info=True)
    return store
