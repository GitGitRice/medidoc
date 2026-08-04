"""Einstiegspunkt der API.

Bewusst kurz: CORS, `/health`, Router einhängen. Endpunkte stehen in den
Modulen unter `app/modules/`, nicht hier.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings

app = FastAPI(title="MediDoc API")

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
