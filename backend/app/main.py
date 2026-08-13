"""Einstiegspunkt der API.

Bewusst kurz: Logging, CORS, Fehlerformat, `/health`, Router einhängen.
Endpunkte stehen in den Modulen unter `app/modules/`, nicht hier.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware

# Als Erstes: Alles, was danach beim Import loggt, soll schon im richtigen
# Format herauskommen.
configure_logging()

app = FastAPI(title="MediDoc API")

# Ein Format für alle Fehlerantworten, siehe app/core/errors.py.
register_error_handlers(app)

# Bearer token in the Authorization header, so no credentialed requests.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Zuletzt hinzugefügt heißt: läuft als Erstes. Der Request-Kontext soll die
# äußerste Schicht sein — dann trägt auch eine von CORS abgewiesene Anfrage
# schon eine Kennung und steht mit ihrer Dauer im Log.
app.add_middleware(RequestContextMiddleware)

app.include_router(api_router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Sagt nur, dass der Prozess läuft — prüft bewusst nicht die Datenbank.

    Wird von Docker Compose im Sekundentakt aufgerufen und deshalb nicht
    geloggt, siehe `QUIET_PATHS` in app/core/middleware.py.
    """
    return {"status": "ok"}
