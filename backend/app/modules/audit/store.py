"""Wo der Audit-Trail liegt.

Zwei Ausführungen hinter derselben Schnittstelle:

- `MongoAuditStore` — der Normalfall. MongoDB räumt über einen TTL-Index selbst
  auf, und die Auswertung („alle Fehlversuche für diese E-Mail in den letzten 15
  Minuten") ist eine gewöhnliche Abfrage über einen Index.
- `MemoryAuditStore` — wenn kein `MONGO_URL` gesetzt ist und in den Tests. Hält
  die letzten Ereignisse im Prozess und ist nach dem Neustart leer.

**Die Anwendung startet in beiden Fällen.** Warum MongoDB und nicht Redis, mit
Messwerten: docs/adr/0007-mongodb-fuer-audit-und-monitoring.md.

Die eiserne Regel dieser Datei: **Ein Fehler beim Protokollieren darf niemals
einen Request kippen.** Ein Arzt, der einen Patienten anlegen will, soll nicht
scheitern, weil die Audit-Datenbank hakt. Alle Schreibfehler werden geschluckt
und als Warnung geloggt — dann fehlt eine Zeile im Trail, aber die Praxis
arbeitet weiter.
"""

import logging
from collections import deque
from datetime import datetime
from typing import Any, Protocol

from app.core.config import settings
from app.modules.audit.events import AuditEvent, EventType

log = logging.getLogger(__name__)

COLLECTION = "audit_events"

# So viele Ereignisse hält die Speicher-Variante vor. Groß genug, dass die
# Erkennung über ihr Zeitfenster arbeiten kann, klein genug, dass ein
# monatelang laufender Prozess nicht vollläuft.
MEMORY_LIMIT = 5000


class AuditStore(Protocol):
    """Was der Trail können muss — mehr braucht die Erkennung nicht."""

    def record(self, event: AuditEvent) -> None:
        """Hängt ein Ereignis an. Wirft nie."""

    def count_since(
        self, event: EventType, field: str, value: object, since: datetime
    ) -> int:
        """Wie oft `event` seit `since` für `field == value` vorkam."""

    def recent(
        self,
        limit: int = 50,
        event: EventType | None = None,
        severity: str | None = None,
    ) -> list[dict[str, Any]]:
        """Die jüngsten Ereignisse, neueste zuerst."""


class MemoryAuditStore:
    """Trail im Prozessspeicher. Für Tests und für den Betrieb ohne Mongo."""

    def __init__(self, limit: int = MEMORY_LIMIT) -> None:
        self._events: deque[AuditEvent] = deque(maxlen=limit)

    def record(self, event: AuditEvent) -> None:
        self._events.append(event)

    def count_since(
        self, event: EventType, field: str, value: object, since: datetime
    ) -> int:
        if value is None:
            return 0
        return sum(
            1
            for e in self._events
            if e.event == event and getattr(e, field, None) == value and e.ts >= since
        )

    def recent(
        self,
        limit: int = 50,
        event: EventType | None = None,
        severity: str | None = None,
    ) -> list[dict[str, Any]]:
        treffer = [
            e
            for e in reversed(self._events)
            if (event is None or e.event == event)
            and (severity is None or e.severity == severity)
        ]
        return [e.model_dump(mode="json") for e in treffer[:limit]]


class MongoAuditStore:
    """Trail in MongoDB — dauerhaft, auswertbar, räumt sich selbst auf."""

    def __init__(self, url: str, database: str, retention_days: int) -> None:
        # Erst hier importiert, damit `pymongo` keine harte Abhängigkeit für
        # alle ist, die die Anwendung nur mit der Speicher-Variante starten.
        from pymongo import ASCENDING, DESCENDING, MongoClient

        self._client: Any = MongoClient(
            url,
            # Zeitpunkte kommen mit Zeitzone zurück. Ohne das wäre `ts` beim
            # Lesen aus Mongo ein `datetime` ohne `tzinfo` und stünde in der
            # Antwort ohne `Z` — anders als beim Speicher-Trail, der dasselbe
            # Ereignis mit `Z` ausliefert. Ein Trail, dessen Zeitstempel je nach
            # Speicher anders zu lesen ist, taugt nicht als Beleg.
            tz_aware=True,
            # Kurz halten: Wenn Mongo weg ist, soll ein Request nicht sekundenlang
            # hängen, nur weil sein Protokolleintrag nicht wegkommt.
            serverSelectionTimeoutMS=2000,
            connectTimeoutMS=2000,
            socketTimeoutMS=2000,
        )
        self._collection = self._client[database][COLLECTION]
        self._ascending = ASCENDING
        self._descending = DESCENDING
        self._retention_days = retention_days

    def ensure_indexes(self) -> None:
        """Legt die Indizes an. Beim Start aufgerufen, verträgt Wiederholung.

        Ohne die Zähl-Indizes würde jede Erkennungsregel die ganze Collection
        lesen — bei einem Trail, der pro Tag wächst, wäre das der Punkt, an dem
        das Protokollieren die Anwendung ausbremst.
        """
        try:
            self._collection.create_index(
                [("ts", self._ascending)],
                # MongoDB löscht abgelaufene Einträge selbst. Ohne das müsste
                # jemand aufräumen — und niemand tut das.
                expireAfterSeconds=self._retention_days * 24 * 60 * 60,
                name="ttl_ts",
            )
            for feld in ("email", "ip", "user_id"):
                self._collection.create_index(
                    [("event", self._ascending), (feld, self._ascending), ("ts", self._descending)],
                    name=f"event_{feld}_ts",
                )
            self._collection.create_index(
                [("severity", self._ascending), ("ts", self._descending)],
                name="severity_ts",
            )
        except Exception:
            log.warning("audit: Indizes konnten nicht angelegt werden", exc_info=True)

    def record(self, event: AuditEvent) -> None:
        try:
            self._collection.insert_one(event.model_dump())
        except Exception:
            # Bewusst geschluckt: siehe Modul-Docstring.
            log.warning(
                "audit: Ereignis nicht geschrieben",
                extra={"event": event.event, "reason": "mongo_unavailable"},
            )

    def count_since(
        self, event: EventType, field: str, value: object, since: datetime
    ) -> int:
        if value is None:
            return 0
        try:
            return self._collection.count_documents(
                {"event": event, field: value, "ts": {"$gte": since}}
            )
        except Exception:
            log.warning("audit: Zählung fehlgeschlagen", exc_info=True)
            # Null heißt: keine Erkennung. Lieber eine verpasste Warnung als
            # ein Fehlalarm oder ein kaputter Request.
            return 0

    def recent(
        self,
        limit: int = 50,
        event: EventType | None = None,
        severity: str | None = None,
    ) -> list[dict[str, Any]]:
        filter_: dict[str, Any] = {}
        if event is not None:
            filter_["event"] = event
        if severity is not None:
            filter_["severity"] = severity
        try:
            treffer = (
                self._collection.find(filter_, {"_id": False})
                .sort("ts", self._descending)
                .limit(limit)
            )
            return [_serialisierbar(dokument) for dokument in treffer]
        except Exception:
            log.warning("audit: Abfrage fehlgeschlagen", exc_info=True)
            return []


def _serialisierbar(dokument: dict[str, Any]) -> dict[str, Any]:
    """`datetime` aus Mongo in ISO-Text, damit FastAPI es ohne Umweg ausgibt.

    `Z` und nicht `+00:00`: Beides ist dieselbe Zeit und gültiges ISO-8601, aber
    der Speicher-Trail geht durch Pydantic und schreibt `Z`. Stünde hier das
    andere, hiesse derselbe Zeitpunkt je nach Speicher anders — und
    docs/logging-monitoring.md zeigt `Z`.
    """
    if isinstance(dokument.get("ts"), datetime):
        dokument["ts"] = dokument["ts"].isoformat().replace("+00:00", "Z")
    return dokument


_store: AuditStore | None = None


def get_store() -> AuditStore:
    """Der Trail dieser Anwendung. Beim ersten Aufruf gebaut."""
    global _store
    if _store is None:
        _store = _build_store()
    return _store


def set_store(store: AuditStore | None) -> None:
    """Setzt den Trail — für Tests, und um ihn wieder zurückzusetzen."""
    global _store
    _store = store


def _build_store() -> AuditStore:
    if not settings.mongo_url:
        log.info("audit: kein MONGO_URL gesetzt, Trail läuft im Speicher")
        return MemoryAuditStore()

    try:
        store = MongoAuditStore(
            settings.mongo_url, settings.mongo_db, settings.audit_retention_days
        )
        store.ensure_indexes()
        log.info(
            "audit: Trail in MongoDB",
            extra={"database": settings.mongo_db, "retention_days": settings.audit_retention_days},
        )
        return store
    except Exception:
        # Auch das ist kein Grund, die Anwendung nicht zu starten.
        log.warning(
            "audit: MongoDB nicht erreichbar, Trail läuft im Speicher", exc_info=True
        )
        return MemoryAuditStore()
