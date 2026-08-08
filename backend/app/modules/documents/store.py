"""Die Angaben zu den Dokumenten — in MongoDB.

Zwei Ausführungen hinter derselben Schnittstelle, wie beim Audit-Trail:
`MongoDocumentStore` für den Betrieb, `MemoryDocumentStore` **nur für die
Tests**, die ihn über `set_store` selbst einsetzen.

**Anders als beim Audit-Trail werden Fehler hier nicht geschluckt.** Ein
verlorener Protokolleintrag ist ärgerlich; ein Anlegen, das „ok" meldet und
dessen Dokument danach nirgends auftaucht, ist schlimmer als eine
Fehlermeldung. Was hier schiefgeht, wird zur Antwort.

Aus demselben Grund gibt es **keinen stillen Rückfall in den Speicher**: Ohne
`MONGO_URL` liefert `get_store()` keinen Ersatz, sondern einen Fehler. Der
Audit-Trail darf ohne Mongo weiterlaufen — ein verlorenes Protokoll ist kein
verlorener Befund —, die Akte eines Patienten nicht (ADR-0002, ADR-0007).
"""

import re
from typing import Any, Protocol

COLLECTION = "documents"


# Worin `q` sucht. **Beide** Ausführungen lesen diese Liste — sonst fände die
# eine etwas, das die andere nicht findet, und weil die Tests gegen den
# Speicher-Store laufen, fiele ausgerechnet der Mongo-Fall niemandem auf.
SEARCHED_FIELDS = ("title", "description")


def normalize_term(q: str | None) -> str:
    """Der Suchbegriff, wie ihn beide Speicher sehen: getrimmt, kleingeschrieben."""
    return (q or "").strip().lower()


def matches_term(document: dict[str, Any], term: str) -> bool:
    """Trifft `term` in einem der durchsuchten Felder?

    Ein leerer Begriff trifft alles — „keine Suche" ist kein Filter.
    """
    if not term:
        return True
    return any(
        term in (document.get(field) or "").lower() for field in SEARCHED_FIELDS
    )


def _search_filter(patient_id: int, q: str | None) -> dict[str, Any]:
    """Derselbe Filter als Mongo-Kriterium — für Liste und Zählung.

    `re.escape` ist hier nicht Kosmetik: Ohne das wäre eine Suche nach `.*` ein
    Ausdruck, der alles findet, und eine nach `(` ein Fehler.
    """
    query: dict[str, Any] = {"patient_id": patient_id}

    term = normalize_term(q)
    if term:
        pattern = re.escape(term)
        query["$or"] = [
            {field: {"$regex": pattern, "$options": "i"}} for field in SEARCHED_FIELDS
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
    """Metadaten im Prozessspeicher — für die Tests.

    Bewusst **nicht** der Rückfall im Betrieb: Ein Dokument, das den Neustart
    nicht überlebt, ist ein verlorener Befund. Wer ihn braucht, setzt ihn über
    `set_store` selbst ein.
    """

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
        term = normalize_term(q)

        found = [
            document
            for document in self._documents
            if document["patient_id"] == patient_id and matches_term(document, term)
        ]
        # Neueste zuerst, `_id` als Stichentscheid — sonst wechselte die
        # Reihenfolge bei gleichem Zeitstempel und das Blättern zeigte
        # Dokumente doppelt.
        found.sort(key=lambda d: (d["created_at"], d["_id"]), reverse=True)

        return [dict(d) for d in found[offset : offset + limit]], len(found)

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

        found = (
            self._collection.find(query)
            .sort([("created_at", self._descending), ("_id", self._descending)])
            .skip(offset)
            .limit(limit)
        )

        return list(found), self._collection.count_documents(query)

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
        # Kein Rückfall in den Speicher. Der wäre die freundlichere Antwort und
        # die falsche: Das Anlegen meldete `201`, der Anhang läge wirklich auf
        # der Platte, und nach dem nächsten Neustart wäre das Dokument weg —
        # ohne dass irgendwo etwas schiefgegangen wäre. Lieber gar kein
        # Dokument als eines, auf das sich niemand verlassen kann.
        log.error("documents: MONGO_URL ist nicht gesetzt, kein Dokumentenspeicher")
        raise RuntimeError(
            "MONGO_URL ist nicht gesetzt — Dokumente brauchen MongoDB (ADR-0002)"
        )

    store = MongoDocumentStore(settings.mongo_url, settings.mongo_db)
    try:
        store.ensure_indexes()
    except Exception:
        # Ein fehlender Index macht die Liste langsam, nicht falsch — das ist
        # kein Grund, die Anwendung nicht zu starten. Schreib- und Lesefehler
        # kommen später sehr wohl durch.
        log.warning("documents: Indizes konnten nicht angelegt werden", exc_info=True)
    return store
