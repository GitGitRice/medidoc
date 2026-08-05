"""Eine Zeile pro Anfrage — und die sicherheitsrelevanten Fälle in den Trail.

Reines ASGI statt `BaseHTTPMiddleware`: Letzteres führt die Anwendung in einer
eigenen Task aus und puffert die Antwort. Für eine Schicht, die nur eine
Kennung setzt, misst und protokolliert, ist das unnötig — und sie soll später
auch dann nicht im Weg stehen, wenn ein Endpunkt eine Datei streamt.

Was hier entsteht, hängt an genau einer Stelle und gilt damit für **jeden**
Endpunkt, auch für einen, den morgen jemand dazuschreibt. Genau deshalb steht
es hier und nicht in den Routern.

Drei Ereignisarten leitet diese Schicht aus dem Statuscode ab — die, die man
allein am Ergebnis erkennt:

| Status | Ereignis | Warum es zählt |
| ------ | -------- | -------------- |
| `401` (nicht am Login) | `token_rejected` | jemand probiert Token durch |
| `403` | `forbidden` | angemeldeter Benutzer klopft an fremde Türen |
| `404` | `not_found` | gehäuft: jemand zählt Kennungen durch |

Alles, was den Rumpf kennen muss — der fehlgeschlagene Login mit der versuchten
E-Mail, das Anlegen eines Patienten mit seiner neuen ID —, wird dort
festgehalten, wo diese Angaben vorliegen: im jeweiligen Router.
"""

import logging
import time
from uuid import uuid4

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import request_id_var

log = logging.getLogger("medidoc.request")

# Der Login beantwortet falsche Zugangsdaten selbst mit `401` und schreibt sein
# eigenes, genaueres Ereignis. Ohne diese Ausnahme stünde jeder Fehlversuch
# doppelt im Trail.
LOGIN_PATH = "/auth/login"

# Aufrufe, die im Sekundentakt kommen und nichts aussagen. Ein Healthcheck alle
# fünf Sekunden macht sonst das halbe Log aus.
QUIET_PATHS = frozenset({"/health"})


class RequestContextMiddleware:
    """Vergibt die Anfrage-Kennung, misst die Dauer, schreibt die Logzeile."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid4().hex
        token = request_id_var.set(request_id)
        start = time.perf_counter()

        # Wird von `send_wrapper` gefüllt. 500 als Vorgabe: Bricht die
        # Anwendung ab, ohne je eine Antwort zu beginnen, ist das die Wahrheit.
        antwort = {"status": 500}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                antwort["status"] = message["status"]
                # Damit eine Meldung im Frontend und die Zeile im Server-Log
                # dieselbe Kennung tragen.
                MutableHeaders(scope=message).append("X-Request-ID", request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            dauer_ms = (time.perf_counter() - start) * 1000
            try:
                self._nachbereiten(scope, antwort["status"], dauer_ms, request_id)
            finally:
                # Muss auch dann zurückgesetzt werden, wenn das Protokollieren
                # selbst schiefgeht — sonst leckt die Kennung in den nächsten
                # Request, der denselben Kontext erbt.
                request_id_var.reset(token)

    def _nachbereiten(
        self, scope: Scope, status: int, dauer_ms: float, request_id: str
    ) -> None:
        # Erst hier importiert: `audit.service` zieht die Konfiguration und den
        # Store nach sich, und diese Datei wird sehr früh geladen.
        from app.modules.audit import service as audit
        from app.modules.audit.events import EventType

        request = Request(scope)
        pfad = scope.get("path", "")
        # `get_current_user` legt die ID hier ab, sobald der Token gültig war.
        user_id = scope.get("state", {}).get("user_id")

        if pfad not in QUIET_PATHS:
            log.log(
                _level(status),
                "%s %s -> %s",
                scope.get("method", "?"),
                pfad,
                status,
                extra={
                    "method": scope.get("method"),
                    "path": pfad,
                    "status": status,
                    "duration_ms": round(dauer_ms, 1),
                    "user_id": user_id,
                    "ip": audit.client_ip(request),
                },
            )

        ereignis = self._ereignis_fuer(status, pfad)
        if ereignis is None:
            return

        audit.record(
            ereignis,
            request=request,
            status=status,
            user_id=user_id,
            target=_target(pfad),
        )

    @staticmethod
    def _ereignis_fuer(status: int, pfad: str) -> "EventType | None":  # type: ignore[name-defined] # noqa: F821
        from app.modules.audit.events import EventType

        if status == 401 and pfad != LOGIN_PATH:
            return EventType.TOKEN_REJECTED
        if status == 403:
            return EventType.FORBIDDEN
        if status == 404:
            return EventType.NOT_FOUND
        return None


def _level(status: int) -> int:
    if status >= 500:
        return logging.ERROR
    if status >= 400:
        return logging.WARNING
    return logging.INFO


def _target(pfad: str) -> str | None:
    """`/patienten/42` wird zu `patient:42`.

    Nur die Kennung, nie der Patient selbst — siehe `audit/events.py`.
    """
    teile = [t for t in pfad.split("/") if t]
    if len(teile) == 2 and teile[0] == "patienten" and teile[1].isdigit():
        return f"patient:{teile[1]}"
    return None
