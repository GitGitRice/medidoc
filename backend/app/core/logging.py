"""Strukturiertes Logging — die unterste der drei Schichten.

Siehe docs/logging-monitoring.md. Kurz:

1. **Log** (hier): jede Anfrage eine Zeile auf stdout. Flüchtig, holt `docker
   compose logs` ab. Zum Nachsehen, was der Server gerade tut.
2. **Audit-Trail** (`app/modules/audit/`): nur sicherheitsrelevante Ereignisse,
   dauerhaft in MongoDB, auswertbar.
3. **Erkennung**: zählt über den Trail und schlägt an.

Zwei Ausgabeformen, eine Einstellung: `LOG_JSON=false` schreibt eine lesbare
Zeile fürs Terminal, `LOG_JSON=true` eine JSON-Zeile pro Ereignis, wie ein
Log-Sammler sie erwartet. Der Inhalt ist derselbe.

**Was hier niemals hineingehört**, siehe `REDACTED_KEYS`: Passwörter, Token,
Hashes — und keine Patientendaten. Ein Log landet in Dateien, in der Konsole und
womöglich in einem Sammeldienst; ein Patientenname hat dort nichts verloren.
Geloggt wird die `id`, nicht der Mensch.
"""

import json
import logging
import sys
from contextvars import ContextVar
from typing import Any

from app.core.config import settings

# Die Anfrage-Kennung reist durch den ganzen Request, ohne dass sie jede
# Funktion als Parameter durchreichen muss. Sie steht in jeder Logzeile, in
# jedem Audit-Ereignis und im Antwort-Header `X-Request-ID` — damit lässt sich
# eine Meldung im Frontend mit der Zeile im Server-Log zusammenbringen.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# Felder, deren Wert nie im Klartext auftaucht — egal, wer sie mitgibt.
REDACTED_KEYS = frozenset(
    {
        "password",
        "passwort",
        "password_hash",
        "token",
        "access_token",
        "authorization",
        "jwt_secret",
        "secret",
    }
)

REDACTED = "***"

# Attribute, die jeder LogRecord von Haus aus mitbringt. Alles, was *nicht*
# hier steht, ist ein selbst mitgegebenes Feld und wandert in die Ausgabe.
_STANDARD_ATTRS = frozenset(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__
) | {"message", "asctime", "taskName"}


def redact(daten: dict[str, Any]) -> dict[str, Any]:
    """Ersetzt die Werte verräterischer Felder, rekursiv."""
    sauber: dict[str, Any] = {}
    for schluessel, wert in daten.items():
        if schluessel.lower() in REDACTED_KEYS:
            sauber[schluessel] = REDACTED
        elif isinstance(wert, dict):
            sauber[schluessel] = redact(wert)
        else:
            sauber[schluessel] = wert
    return sauber


def _extras(record: logging.LogRecord) -> dict[str, Any]:
    """Die Felder, die der Aufrufer über `extra=` mitgegeben hat."""
    return {
        schluessel: wert
        for schluessel, wert in record.__dict__.items()
        if schluessel not in _STANDARD_ATTRS
    }


class JsonFormatter(logging.Formatter):
    """Eine JSON-Zeile pro Ereignis."""

    def format(self, record: logging.LogRecord) -> str:
        zeile: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        anfrage = request_id_var.get()
        if anfrage:
            zeile["request_id"] = anfrage

        zeile.update(_extras(record))

        if record.exc_info:
            zeile["exception"] = self.formatException(record.exc_info)

        # `default=str` fängt alles ab, was JSON nicht kennt (datetime, Enum).
        # Eine Logzeile darf niemals daran scheitern, dass sie sich nicht
        # serialisieren lässt.
        return json.dumps(redact(zeile), ensure_ascii=False, default=str)


class ConsoleFormatter(logging.Formatter):
    """Eine lesbare Zeile fürs Terminal, mit den Zusatzfeldern hinten dran."""

    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)-7s %(name)-28s %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        basis = super().format(record)

        felder = redact(_extras(record))
        anfrage = request_id_var.get()
        if anfrage:
            felder = {"request_id": anfrage[:8], **felder}

        if not felder:
            return basis

        angehaengt = " ".join(f"{k}={v}" for k, v in felder.items())
        return f"{basis}  {angehaengt}"


def configure_logging() -> None:
    """Richtet das Logging der Anwendung ein. Einmal beim Start aufgerufen.

    Setzt die Handler des Root-Loggers neu, damit nicht Uvicorn und wir
    nebeneinander schreiben und jede Zeile doppelt erscheint.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if settings.log_json else ConsoleFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())

    # Uvicorns eigener Zugriffs-Log doppelt unseren Request-Log, nur ohne
    # Dauer, Benutzer und Anfrage-Kennung. Einer reicht, und zwar unserer.
    logging.getLogger("uvicorn.access").handlers = []
    logging.getLogger("uvicorn.access").propagate = False
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True
