"""Was überhaupt protokolliert wird — und was ausdrücklich nicht.

Der Audit-Trail ist **kein zweites Anwendungslog.** Hier landet nur, was eine
Sicherheitsfrage beantwortet: Wer hat sich angemeldet, wer ist gescheitert, wer
hat an eine Tür geklopft, die ihm nicht offensteht, und wer hat Patientendaten
verändert. Alles andere gehört ins Log auf stdout und ist nach dem Neustart weg.

**Keine Patientendaten.** Ein Ereignis nennt `patient:42`, niemals einen Namen,
ein Geburtsdatum oder eine Versichertennummer. Der Trail liegt dauerhaft in
einer eigenen Datenbank und ist damit genau die Stelle, an der eine unbedachte
Zeile am längsten überlebt. Wer wissen will, *wer* Patient 42 ist, hat dafür die
Patiententabelle — und einen Grund.
"""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class EventType(StrEnum):
    """Die protokollierten Ereignisse.

    Bewusst wenige und grobe: Eine Liste, die niemand mehr überblickt, wird
    nicht ausgewertet.
    """

    # Anmeldung
    LOGIN_SUCCEEDED = "login_succeeded"
    LOGIN_FAILED = "login_failed"

    # Token und Rechte
    TOKEN_REJECTED = "token_rejected"  # 401 an einem geschützten Endpunkt
    FORBIDDEN = "forbidden"  # 403 — angemeldet, aber Rolle reicht nicht

    # Patienten — die schreibenden Zugriffe, lesende wären nur Rauschen
    PATIENT_CREATED = "patient_created"
    PATIENT_UPDATED = "patient_updated"
    PATIENT_DELETED = "patient_deleted"

    # Zugriff auf eine ID, die es nicht gibt. Einzeln harmlos, gehäuft der
    # Fingerabdruck einer ID-Enumeration.
    NOT_FOUND = "not_found"

    # Das Ergebnis der Erkennung, siehe service.detect
    SUSPICIOUS = "suspicious"


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"


# Ereignisse, die im Normalbetrieb vorkommen und trotzdem festgehalten werden.
# Alles andere ist eine Warnung.
_INFO_EVENTS = frozenset(
    {
        EventType.LOGIN_SUCCEEDED,
        EventType.PATIENT_CREATED,
        EventType.PATIENT_UPDATED,
        EventType.PATIENT_DELETED,
    }
)


class AuditEvent(BaseModel):
    """Ein Eintrag im Trail.

    Die drei Felder `email`, `ip` und `user_id` sind zugleich die Achsen, über
    die die Erkennung zählt — deshalb stehen sie flach im Dokument und nicht in
    `detail`, und deshalb hat jede von ihnen einen Index.
    """

    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))
    event: EventType
    severity: Severity = Severity.INFO

    # Verbindet den Eintrag mit der Zeile im Log und dem Header der Antwort.
    request_id: str | None = None

    ip: str | None = None
    # Nur bei Anmeldeversuchen: die *versuchte* E-Mail. Sie ist bei einem
    # Fehlversuch die einzige Spur, welches Konto gemeint war — der Benutzer
    # steht ja gerade nicht fest.
    email: str | None = None
    user_id: int | None = None

    method: str | None = None
    path: str | None = None
    status: int | None = None

    # Was betroffen war, als undurchsichtige Kennung: "patient:42".
    target: str | None = None

    # Platz für den Einzelfall — die Regel, die angeschlagen hat, die Zahl der
    # Treffer. Niemals Nutzdaten.
    detail: dict[str, object] = Field(default_factory=dict)

    @classmethod
    def build(cls, event: EventType, **felder: object) -> "AuditEvent":
        """Baut ein Ereignis und setzt den Schweregrad passend zum Typ."""
        felder.setdefault(
            "severity", Severity.INFO if event in _INFO_EVENTS else Severity.WARNING
        )
        return cls(event=event, **felder)  # type: ignore[arg-type]
