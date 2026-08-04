"""Patientenverwaltung — Endpunkte.

Die Endpunkte übersetzen nur: Eingabe prüfen, `service` aufrufen, Ergebnis in
Statuscode und Response-Model gießen. Fachliche Logik gehört nach `service.py`.

**Noch ungeschützt.** So im Sprint-1-Plan vorgesehen, damit Frontend und
Backend nicht auf den Login warten. Sobald `app/modules/auth/dependencies.py`
steht, kommt an jeden Endpunkt eine Zeile:

    from fastapi import Depends
    from app.modules.auth.dependencies import get_current_user, require_roles
    from app.modules.users.models import Role, User

    def list_patients(..., user: User = Depends(get_current_user)): ...
    def delete_patient(..., user: User = Depends(require_roles(Role.ADMIN))): ...

`require_roles(Role.ADMIN)` bekommt genau `DELETE` — die einzige Stelle im
Sprint 1, die eine Rolle prüft (ADR-0005). Alle anderen `get_current_user`.

**Offen fürs Daily:** Der Pfad heißt hier `/patients`, weil CONTEXT.md und
ADR-0005 festlegen, dass Code und API durchgehend englisch sind. In den
Beispielen in docs/auth-api.md steht dagegen `/patienten`. Das Frontend muss
wissen, was gilt — bis das entschieden ist, gilt der Regel nach `/patients`.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.db.session import get_session
from app.modules.patients import service
from app.modules.patients.models import Patient
from app.modules.patients.schemas import (
    PatientCreate,
    PatientPage,
    PatientPublic,
    PatientUpdate,
)

router = APIRouter(prefix="/patients", tags=["patients"])

SessionDep = Annotated[Session, Depends(get_session)]


@router.get("", response_model=PatientPage)
def list_patients(
    session: SessionDep,
    q: Annotated[
        str | None,
        Query(description="Sucht in Vorname, Nachname und Versichertennummer"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=service.MAX_LIMIT)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PatientPage:
    """Die Patientenübersicht — durchsuchbar und seitenweise."""
    items, total = service.search(session, query=q, limit=limit, offset=offset)
    return PatientPage(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=PatientPublic, status_code=status.HTTP_201_CREATED)
def create_patient(session: SessionDep, data: PatientCreate) -> Patient:
    """Legt einen Patienten an."""
    _reject_taken_insurance_number(session, data.insurance_number)
    return service.create(session, data)


@router.get("/{patient_id}", response_model=PatientPublic)
def get_patient(session: SessionDep, patient_id: int) -> Patient:
    """Die Stammdaten eines Patienten."""
    return _get_or_404(session, patient_id)


@router.patch("/{patient_id}", response_model=PatientPublic)
def update_patient(
    session: SessionDep, patient_id: int, data: PatientUpdate
) -> Patient:
    """Ändert einzelne Stammdaten. Weggelassene Felder bleiben unverändert."""
    patient = _get_or_404(session, patient_id)
    _reject_taken_insurance_number(session, data.insurance_number, exclude_id=patient_id)
    return service.update(session, patient, data)


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_patient(session: SessionDep, patient_id: int) -> None:
    """Löscht einen Patienten endgültig.

    Verlangt später `admin` — siehe Hinweis oben im Modul.
    """
    service.delete(session, _get_or_404(session, patient_id))


def _get_or_404(session: Session, patient_id: int) -> Patient:
    patient = service.get(session, patient_id)
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient nicht gefunden",
        )
    return patient


def _reject_taken_insurance_number(
    session: Session, insurance_number: str | None, exclude_id: int | None = None
) -> None:
    """409 statt eines 500 aus dem Unique-Index der Datenbank.

    Der Index bleibt trotzdem die eigentliche Absicherung — diese Prüfung
    liefert nur die verständlichere Meldung.
    """
    if insurance_number is None:
        return
    if service.insurance_number_taken(session, insurance_number, exclude_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Diese Versichertennummer ist bereits vergeben",
        )
