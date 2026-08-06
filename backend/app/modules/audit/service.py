"""Ereignisse festhalten und Auffälligkeiten erkennen.

Zwei Aufgaben, bewusst in einer Datei, weil sie dieselbe Bewegung sind: Jedes
Ereignis wird geschrieben und **unmittelbar danach** gegen die Regeln gehalten.
Es gibt keinen Hintergrundlauf, der später nachsieht — die Warnung steht in
derselben Sekunde im Log wie das Ereignis, das sie ausgelöst hat.

**Es wird nie blockiert.** Diese Schicht schreibt und warnt, sie lehnt keinen
Request ab. Ein Fehlalarm kostet damit eine Logzeile und nicht die Vorführung.
Wer später drosseln will, hat mit dem Trail die Zahlen, um die Schwelle zu
begründen.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import Request

from app.core.config import settings
from app.core.logging import request_id_var
from app.modules.audit.events import AuditEvent, EventType, Severity
from app.modules.audit.store import AuditStore, get_store

log = logging.getLogger("medidoc.audit")


@dataclass(frozen=True)
class Rule:
    """„Wenn `event` innerhalb des Fensters öfter als `limit` mal für denselben
    `field`-Wert vorkam, ist das auffällig."""

    name: str
    event: EventType
    field: str
    limit: int
    beschreibung: str


def rules() -> list[Rule]:
    """Die Erkennungsregeln, mit den Schwellen aus der Konfiguration.

    Als Funktion und nicht als Modulkonstante, damit ein Test die Schwellen
    umstellen kann, ohne das Modul neu zu laden.
    """
    return [
        Rule(
            "brute_force_email",
            EventType.LOGIN_FAILED,
            "email",
            settings.abuse_failed_logins_per_email,
            "Wiederholte Fehlversuche auf dasselbe Konto",
        ),
        Rule(
            "brute_force_ip",
            EventType.LOGIN_FAILED,
            "ip",
            settings.abuse_failed_logins_per_ip,
            "Wiederholte Fehlversuche von derselben Adresse",
        ),
        Rule(
            "token_probing",
            EventType.TOKEN_REJECTED,
            "ip",
            settings.abuse_rejected_tokens_per_ip,
            "Viele abgewiesene Token von derselben Adresse",
        ),
        Rule(
            "privilege_probing",
            EventType.FORBIDDEN,
            "user_id",
            settings.abuse_forbidden_per_user,
            "Benutzer klopft wiederholt an eine Tür, die ihm nicht offensteht",
        ),
        Rule(
            # Der Fall, der bei Patientendaten wirklich zählt: Jemand zählt IDs
            # durch, um herauszufinden, welche es gibt. Einzeln ist ein 404
            # nichts, gehäuft ist es eine Enumeration.
            "id_enumeration",
            EventType.NOT_FOUND,
            "user_id",
            settings.abuse_not_found_per_user,
            "Viele Zugriffe auf nicht vorhandene Kennungen",
        ),
    ]


def record(event: EventType, request: Request | None = None, **felder: object) -> AuditEvent:
    """Hält ein Ereignis fest, loggt es und prüft die Regeln.

    Gibt das geschriebene Ereignis zurück — praktisch für Tests, im
    Anwendungscode ignoriert man es.

    **Wirft nicht.** Das Schreiben in den Trail und die Erkennung sind
    abgeschirmt: Ein Arzt, der einen Patienten anlegen will, soll nicht
    scheitern, weil die Audit-Datenbank hakt. Dann fehlt eine Zeile im Trail,
    aber die Praxis arbeitet weiter. Die Zusicherung steht bewusst *hier* und
    nicht in `MongoAuditStore` — sie muss für jede Ausführung des Stores
    gelten, auch für eine, die es noch nicht gibt.
    """
    if request is not None:
        felder.setdefault("ip", client_ip(request))
        felder.setdefault("method", request.method)
        felder.setdefault("path", request.url.path)
    felder.setdefault("request_id", request_id_var.get())

    eintrag = AuditEvent.build(event, **felder)

    log.log(
        logging.WARNING if eintrag.severity is Severity.WARNING else logging.INFO,
        "audit %s",
        eintrag.event,
        extra={
            "event": str(eintrag.event),
            **{
                k: v
                for k, v in (
                    ("user_id", eintrag.user_id),
                    ("email", eintrag.email),
                    ("ip", eintrag.ip),
                    ("target", eintrag.target),
                    ("status", eintrag.status),
                )
                if v is not None
            },
        },
    )

    try:
        store = get_store()
        store.record(eintrag)

        # Ein Verdachtsereignis darf keine neue Prüfung auslösen, sonst
        # schaukelt sich das auf.
        if eintrag.event is not EventType.SUSPICIOUS:
            detect(eintrag, store)
    except Exception:
        # Die Logzeile oben ist da schon geschrieben — der Vorfall ist also
        # nicht verloren, nur nicht auswertbar abgelegt.
        log.warning(
            "audit: Ereignis konnte nicht abgelegt werden",
            extra={"event": str(eintrag.event)},
            exc_info=True,
        )

    return eintrag


def detect(eintrag: AuditEvent, store: AuditStore | None = None) -> list[str]:
    """Prüft die Regeln gegen das eben geschriebene Ereignis.

    Gibt die Namen der Regeln zurück, die angeschlagen haben.
    """
    store = store or get_store()
    seit = datetime.now(UTC) - timedelta(minutes=settings.abuse_window_minutes)
    ausgeloest = []

    for regel in rules():
        if regel.event is not eintrag.event:
            continue

        wert = getattr(eintrag, regel.field, None)
        if wert is None:
            continue

        treffer = store.count_since(regel.event, regel.field, wert, seit)

        # Genau auf der Schwelle, nicht darüber: Sonst schriebe jeder weitere
        # Fehlversuch eine neue Warnung und der Trail liefe mit Wiederholungen
        # desselben Befunds voll.
        if treffer != regel.limit:
            continue

        ausgeloest.append(regel.name)
        record(
            EventType.SUSPICIOUS,
            severity=Severity.WARNING,
            ip=eintrag.ip,
            email=eintrag.email,
            user_id=eintrag.user_id,
            request_id=eintrag.request_id,
            detail={
                "rule": regel.name,
                "description": regel.beschreibung,
                "matched_event": str(regel.event),
                "field": regel.field,
                "count": treffer,
                "limit": regel.limit,
                "window_minutes": settings.abuse_window_minutes,
            },
        )

    return ausgeloest


def client_ip(request: Request) -> str | None:
    """Die Adresse des Aufrufers.

    Bewusst aus der Verbindung und **nicht** aus `X-Forwarded-For`: Diesen
    Header darf jeder setzen. Würden wir ihm glauben, könnte sich ein
    Angreifer für jeden Versuch eine neue Adresse ausdenken und liefe damit
    unter jeder Schwelle durch. Sobald wirklich ein Proxy davorsteht, muss das
    hier zusammen mit dessen Konfiguration angefasst werden.
    """
    return request.client.host if request.client else None


def recent(
    limit: int = 50,
    event: EventType | None = None,
    severity: str | None = None,
) -> list[dict[str, object]]:
    """Die jüngsten Ereignisse — für den Monitoring-Endpunkt."""
    return get_store().recent(limit=limit, event=event, severity=severity)
