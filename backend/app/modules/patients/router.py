"""Patientenverwaltung — Endpunkte.

Die Endpunkte übersetzen nur: Eingabe prüfen, `service` aufrufen, Ergebnis in
Statuscode und Response-Model gießen. Fachliche Logik gehört nach `service.py`.

Alle Endpunkte verlangen einen angemeldeten Benutzer. Die Prüfung hängt am
Router, nicht an den einzelnen Funktionen:

    router = APIRouter(..., dependencies=[Depends(get_current_user)])

Damit ist ein neuer Endpunkt automatisch geschützt. Hinge die Dependency an
jeder Funktion einzeln, wäre ein vergessener Parameter ein still ungeschützter
Endpunkt — der Fehler soll in die sichere Richtung fallen.

`require_roles(Role.ADMIN)` kommt zusätzlich an genau `DELETE` — die einzige
Stelle im Sprint 1, die eine Rolle prüft (ADR-0005).

Fehlerantworten haben überall dieselbe Form (`status`, `message`), siehe
`app/core/errors.py`. Welcher Endpunkt womit antworten kann, steht als
`responses=` an der jeweiligen Funktion und landet damit in `/docs` — das ist
die Fassung, die das Frontend liest.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.core.errors import ErrorResponse
from app.db.session import get_session
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.patients import service
from app.modules.patients.models import Patient
from app.modules.patients.schemas import (
    PatientCreate,
    PatientPage,
    PatientPublic,
    PatientUpdate,
)
from app.modules.users.models import Role, User

router = APIRouter(
    prefix="/patienten",
    tags=["patienten"],
    dependencies=[Depends(get_current_user)],
)

SessionDep = Annotated[Session, Depends(get_session)]
AdminUser = Annotated[User, Depends(require_roles(Role.ADMIN))]

# Einmal beschrieben, an jedem Endpunkt wiederverwendet — sonst driften die
# Beschreibungen auseinander, sobald jemand eine davon anfasst.
UNAUTHORIZED = {"model": ErrorResponse, "description": "Nicht angemeldet"}
FORBIDDEN = {"model": ErrorResponse, "description": "Rolle reicht nicht"}
NOT_FOUND = {"model": ErrorResponse, "description": "Patient nicht gefunden"}
CONFLICT = {"model": ErrorResponse, "description": "Versichertennummer vergeben"}
UNPROCESSABLE = {"model": ErrorResponse, "description": "Eingabe ungültig"}


@router.get(
    "",
    response_model=PatientPage,
    summary="Patientenübersicht",
    responses={401: UNAUTHORIZED, 422: UNPROCESSABLE},
)
def list_patients(
    session: SessionDep,
    suche: Annotated[
        str | None,
        Query(
            description=(
                "Filtert nach Vorname, Nachname und Versichertennummer. "
                "Groß- und Kleinschreibung egal, Teiltreffer erlaubt. "
                "Mehrere Wörter werden UND-verknüpft."
            ),
            examples=["mustermann", "max muster"],
        ),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=service.MAX_LIMIT)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PatientPage:
    """Alle Patienten, durchsuchbar und seitenweise.

    Findet die Suche nichts, ist `items` eine leere Liste und `total` gleich
    null — das ist **kein** Fehler und wird mit `200` beantwortet.
    """
    # Der Query-Parameter heißt deutsch wie der Pfad, die Service-Schicht
    # englisch wie der übrige Code. Die Übersetzung passiert genau hier.
    items, total = service.search(session, query=suche, limit=limit, offset=offset)
    return PatientPage(items=items, total=total, limit=limit, offset=offset)


@router.post(
    "",
    response_model=PatientPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Patient anlegen",
    responses={401: UNAUTHORIZED, 409: CONFLICT, 422: UNPROCESSABLE},
)
def create_patient(session: SessionDep, data: PatientCreate) -> Patient:
    """Legt einen Patienten an und gibt ihn mit vergebener `id` zurück.

    Fehlt ein Pflichtfeld, antwortet die API mit `422` und nennt in `message`
    und `errors`, welches Feld es ist.
    """
    _reject_taken_insurance_number(session, data.insurance_number)
    return service.create(session, data)


@router.get(
    "/{patient_id}",
    response_model=PatientPublic,
    summary="Patient lesen",
    responses={401: UNAUTHORIZED, 404: NOT_FOUND},
)
def get_patient(session: SessionDep, patient_id: int) -> Patient:
    """Die Stammdaten eines Patienten."""
    return _get_or_404(session, patient_id)


@router.patch(
    "/{patient_id}",
    response_model=PatientPublic,
    summary="Stammdaten ändern",
    responses={
        401: UNAUTHORIZED,
        404: NOT_FOUND,
        409: CONFLICT,
        422: UNPROCESSABLE,
    },
)
def update_patient(
    session: SessionDep, patient_id: int, data: PatientUpdate
) -> Patient:
    """Ändert nur die mitgeschickten Felder und gibt den ganzen Patienten zurück.

    Weggelassene Felder bleiben unverändert. Ein optionales Feld lässt sich mit
    `null` leeren; die drei Pflichtfelder dürfen weggelassen, aber nicht auf
    `null` gesetzt werden.
    """
    patient = _get_or_404(session, patient_id)
    _reject_taken_insurance_number(session, data.insurance_number, exclude_id=patient_id)
    return service.update(session, patient, data)


@router.delete(
    "/{patient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Patient löschen",
    responses={401: UNAUTHORIZED, 403: FORBIDDEN, 404: NOT_FOUND},
)
def delete_patient(session: SessionDep, _user: AdminUser, patient_id: int) -> None:
    """Löscht einen Patienten endgültig — nur als `admin`.

    Zweimaliges Löschen ist kein Serverfehler: Der zweite Aufruf findet den
    Patienten nicht mehr und antwortet mit `404`.
    """
    service.delete(session, _get_or_404(session, patient_id))


def _get_or_404(session: Session, patient_id: int) -> Patient:
    """Der Patient, oder ein `404`, das die gesuchte ID nennt."""
    patient = service.get(session, patient_id)
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient mit der ID {patient_id} wurde nicht gefunden",
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
            detail=(
                f"Die Versichertennummer {insurance_number} ist bereits "
                "einem anderen Patienten zugeordnet"
            ),
        )
