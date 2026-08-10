"""Ein Format für alle Fehlerantworten der API.

FastAPI antwortet von Haus aus mit `{"detail": ...}` — mal ein String, mal
eine Liste. Das Frontend müsste also je nach Statuscode anders auspacken.
Stattdessen sieht **jede** Fehlerantwort gleich aus:

    { "status": 404, "message": "Patient mit der ID 42 wurde nicht gefunden" }

`status` wiederholt den HTTP-Status im Rumpf. Das ist bewusst redundant: In
`catch`-Zweigen und in Logs liegt oft nur noch der geparste Rumpf vor, und dann
fehlt sonst genau die Information, die den Fall einordnet.

`detail` bleibt zusätzlich erhalten, in genau der Form, die FastAPI selbst
erzeugt hätte. Damit brechen weder bestehender Frontend-Code noch die
Auth-Tests, die `detail` prüfen. Neuer Code liest `message`; sobald nichts mehr
auf `detail` zugreift, kann es weg.

Bei `422` kommt `errors` dazu — ein Eintrag pro beanstandetem Feld, damit das
Formular die Meldung an der richtigen Stelle anzeigen kann.
"""

from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException


class FieldError(BaseModel):
    """Ein beanstandetes Feld."""

    field: str
    message: str


class ErrorResponse(BaseModel):
    """Die Form jeder Fehlerantwort — nur zur Dokumentation in `/docs`."""

    status: int
    message: str
    errors: list[FieldError] | None = None


# Für Fehler, die nicht wir auslösen, sondern das Framework: eine unbekannte
# URL, eine falsche Methode. Ohne diese Tabelle stünde dort englischer
# Starlette-Standardtext mitten in einer sonst deutschen API.
_FRAMEWORK_MESSAGES = {
    401: "Anmeldung erforderlich",
    403: "Dazu fehlt dir die Berechtigung",
    404: "Diese Adresse gibt es nicht",
    405: "Diese Methode ist für diese Adresse nicht erlaubt",
    500: "Unerwarteter Fehler im Server",
}

# Pydantic meldet englisch. Übersetzt werden nur die Typen, die bei unseren
# Eingaben wirklich vorkommen — der Rest fällt auf den Originaltext zurück,
# was allemal besser ist als eine falsche Übersetzung.
_TYPE_MESSAGES = {
    "missing": "Feld ist erforderlich",
    "string_type": "Muss Text sein",
    "int_parsing": "Muss eine ganze Zahl sein",
    "int_type": "Muss eine ganze Zahl sein",
    "date_parsing": "Muss ein Datum im Format JJJJ-MM-TT sein",
    "date_type": "Muss ein Datum im Format JJJJ-MM-TT sein",
    "date_from_datetime_inexact": "Muss ein Datum im Format JJJJ-MM-TT sein",
    "enum": "Unzulässiger Wert",
    "greater_than_equal": "Wert ist zu klein",
    "less_than_equal": "Wert ist zu groß",
}


def register_error_handlers(app: FastAPI) -> None:
    """Hängt die Handler in die App. Wird einmal in `main.py` aufgerufen."""
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)


async def _http_error(request: Request, exc: Exception) -> JSONResponse:
    """Alles, was als `HTTPException` geworfen wurde."""
    assert isinstance(exc, StarletteHTTPException)

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": exc.status_code,
            "message": _message_for(exc),
            "detail": exc.detail,
        },
        # Ohne das verlöre ein 401 seinen WWW-Authenticate-Header — der gehört
        # laut HTTP-Standard dazu und lässt den Authorize-Button in /docs
        # richtig reagieren.
        headers=getattr(exc, "headers", None),
    )


async def _validation_error(request: Request, exc: Exception) -> JSONResponse:
    """Eingaben, die schon an der Form scheitern — immer `422`."""
    assert isinstance(exc, RequestValidationError)

    errors = [
        {"field": _field_name(raw["loc"]), "message": _field_message(raw)}
        for raw in exc.errors()
    ]

    return JSONResponse(
        status_code=HTTPStatus.UNPROCESSABLE_CONTENT,
        content={
            "status": int(HTTPStatus.UNPROCESSABLE_CONTENT),
            "message": _validation_summary(exc.errors(), errors),
            "errors": errors,
            "detail": jsonable_encoder(exc.errors()),
        },
    )


def _message_for(exc: StarletteHTTPException) -> str:
    """Unsere eigene Meldung, sonst eine deutsche für den Framework-Fall.

    Erkennbar sind die Framework-Fälle daran, dass `detail` genau der englische
    Standardtext zum Statuscode ist — den schreibt niemand von Hand hin.
    """
    if isinstance(exc.detail, str):
        try:
            standardtext = HTTPStatus(exc.status_code).phrase
        except ValueError:
            standardtext = None
        if exc.detail and exc.detail != standardtext:
            return exc.detail

    return _FRAMEWORK_MESSAGES.get(exc.status_code, "Die Anfrage ist fehlgeschlagen")


def _field_name(loc: tuple[object, ...]) -> str:
    """`("body", "last_name")` wird zu `"last_name"`.

    Das erste Element sagt nur, *wo* der Wert stand (Rumpf, Query, Pfad). Für
    das Formular zählt der Feldname; bei verschachtelten Feldern bleibt der
    Pfad mit Punkten erhalten.
    """
    parts = [str(part) for part in loc]
    if len(parts) > 1 and parts[0] in {"body", "query", "path", "header", "cookie"}:
        parts = parts[1:]
    return ".".join(parts)


def _field_message(raw: dict[str, object]) -> str:
    """Die Meldung zu einem Feld, auf Deutsch wo möglich."""
    if raw.get("type") in _TYPE_MESSAGES:
        return _TYPE_MESSAGES[str(raw["type"])]

    message = str(raw.get("msg", "Ungültiger Wert"))
    # Unsere eigenen Validatoren melden deutsch, Pydantic stellt aber
    # "Value error, " davor.
    return message.removeprefix("Value error, ")


def _validation_summary(
    raw_errors: list[dict[str, object]], errors: list[dict[str, str]]
) -> str:
    """Eine Zeile, die sagt, was los ist — mit Feldnamen.

    Fehlende Pflichtfelder werden zuerst genannt: Das ist der häufigste Fall
    und der einzige, bei dem der Feldname allein schon die ganze Auskunft ist.
    """
    fehlend = [
        error["field"]
        for raw, error in zip(raw_errors, errors, strict=True)
        if raw.get("type") == "missing"
    ]
    if fehlend:
        felder = ", ".join(fehlend)
        return (
            f"Pflichtfeld fehlt: {felder}"
            if len(fehlend) == 1
            else f"Pflichtfelder fehlen: {felder}"
        )

    if len(errors) == 1:
        return f"Ungültige Eingabe für '{errors[0]['field']}': {errors[0]['message']}"

    felder = ", ".join(error["field"] for error in errors)
    return f"Ungültige Eingabe in {len(errors)} Feldern: {felder}"
