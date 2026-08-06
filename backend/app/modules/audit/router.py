"""Monitoring — der Blick in den Audit-Trail.

Nur für `admin`. Der Trail sagt, wer wann was getan hat; wer ihn lesen darf,
sieht damit auch, welche Konten es gibt und wann jemand arbeitet. Das ist keine
Auskunft für alle, die sich anmelden können.

Bewusst nur lesend. Ein Audit-Trail, den man über die API ändern oder löschen
kann, ist keiner. Aufgeräumt wird ausschließlich über den TTL-Index von MongoDB.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.config import settings
from app.core.errors import ErrorResponse
from app.modules.audit import service
from app.modules.audit.events import EventType, Severity
from app.modules.auth.dependencies import require_roles
from app.modules.users.models import Role, User

router = APIRouter(
    prefix="/monitoring",
    tags=["monitoring"],
    dependencies=[Depends(require_roles(Role.ADMIN))],
)

AdminOnly = {
    401: {"model": ErrorResponse, "description": "Nicht angemeldet"},
    403: {"model": ErrorResponse, "description": "Nur für admin"},
}


@router.get("/ereignisse", summary="Audit-Trail lesen", responses=AdminOnly)
def list_events(
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    event: Annotated[EventType | None, Query(description="Nur diese Ereignisart")] = None,
    severity: Annotated[Severity | None, Query(description="Nur diesen Schweregrad")] = None,
) -> list[dict[str, object]]:
    """Die jüngsten Ereignisse, neueste zuerst.

    `?severity=warning` zeigt genau das, was man im Alltag sehen will:
    Fehlversuche, abgewiesene Token, abgewehrte Zugriffe und die Treffer der
    Erkennung.
    """
    return service.recent(limit=limit, event=event, severity=severity)


@router.get("/regeln", summary="Erkennungsregeln und Schwellen", responses=AdminOnly)
def list_rules(_admin: Annotated[User, Depends(require_roles(Role.ADMIN))]) -> dict[str, object]:
    """Welche Regeln greifen und ab wann.

    Steht als Endpunkt zur Verfügung, damit die Schwellen nicht nur in einer
    `.env` auf irgendeinem Rechner stehen, sondern nachsehbar sind — beim
    Vorführen ist genau das die Frage, die kommt.
    """
    return {
        "window_minutes": settings.abuse_window_minutes,
        "retention_days": settings.audit_retention_days,
        "rules": [
            {
                "name": regel.name,
                "event": str(regel.event),
                "field": regel.field,
                "limit": regel.limit,
                "description": regel.beschreibung,
            }
            for regel in service.rules()
        ],
    }
