"""Einstiegspunkt der API.

Bewusst kurz: CORS, Fehlerformat, `/health`, Router einhängen. Endpunkte stehen
in den Modulen unter `app/modules/`, nicht hier.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.errors import register_error_handlers

app = FastAPI(title="MediDoc API")

# Ein Format für alle Fehlerantworten, siehe app/core/errors.py. Muss vor dem
# Einhängen der Router nicht stehen, gehört aber der Lesbarkeit halber hierhin.
register_error_handlers(app)

# Bearer token in the Authorization header, so no credentialed requests.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Sagt nur, dass der Prozess läuft — prüft bewusst nicht die Datenbank."""
    return {"status": "ok"}
