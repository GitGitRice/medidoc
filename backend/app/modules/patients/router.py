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

Pfad, Query-Parameter und JSON-Keys sind englisch (`/patients`, `?q=`). Deutsch
sind nur Kommentare, Doku und die Oberfläche im Frontend — so steht die Regel in
ADR-0005 und in beiden API-Verträgen. ADR-0005 nennt im Fließtext weiterhin
`/patienten`; eine angenommene Entscheidung wird nicht nachträglich
umgeschrieben, verbindlich ist der Code hier.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlmodel import Session

from app.core.errors import ErrorResponse
from app.db.session import get_session
from app.modules.audit import service as audit
from app.modules.audit.events import EventType
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.documents import service as documents_service
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
    prefix="/patients",
    tags=["patients"],
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
    q: Annotated[
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
    items, total = service.search(session, query=q, limit=limit, offset=offset)
    return PatientPage(items=items, total=total, limit=limit, offset=offset)


@router.post(
    "",
    response_model=PatientPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Patient anlegen",
    responses={401: UNAUTHORIZED, 409: CONFLICT, 422: UNPROCESSABLE},
)
def create_patient(request: Request, session: SessionDep, data: PatientCreate) -> Patient:
    """Legt einen Patienten an und gibt ihn mit vergebener `id` zurück.

    Fehlt ein Pflichtfeld, antwortet die API mit `422` und nennt in `message`
    und `errors`, welches Feld es ist.
    """
    _reject_taken_insurance_number(session, data.insurance_number)
    patient = service.create(session, data)
    _audit(request, EventType.PATIENT_CREATED, patient, status.HTTP_201_CREATED)
    return patient


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
    request: Request, session: SessionDep, patient_id: int, data: PatientUpdate
) -> Patient:
    """Ändert nur die mitgeschickten Felder und gibt den ganzen Patienten zurück.

    Weggelassene Felder bleiben unverändert. Ein optionales Feld lässt sich mit
    `null` leeren; die drei Pflichtfelder dürfen weggelassen, aber nicht auf
    `null` gesetzt werden.
    """
    patient = _get_or_404(session, patient_id)
    _reject_taken_insurance_number(session, data.insurance_number, exclude_id=patient_id)
    updated = service.update(session, patient, data)
    # Welche Felder angefasst wurden, nicht womit sie gefüllt wurden — der
    # Trail hält keine Patientendaten.
    _audit(
        request,
        EventType.PATIENT_UPDATED,
        updated,
        status.HTTP_200_OK,
        fields=sorted(data.model_dump(exclude_unset=True)),
    )
    return updated


@router.delete(
    "/{patient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Patient löschen",
    responses={401: UNAUTHORIZED, 403: FORBIDDEN, 404: NOT_FOUND},
)
def delete_patient(
    request: Request, session: SessionDep, _user: AdminUser, patient_id: int
) -> None:
    """Löscht einen Patienten endgültig — nur als `admin`.

    Zweimaliges Löschen ist kein Serverfehler: Der zweite Aufruf findet den
    Patienten nicht mehr und antwortet mit `404`.
    """
    patient = _get_or_404(session, patient_id)
    service.delete(session, patient)

    # Die Akte geht mit. Ohne das blieben Dokumente und Dateien liegen: über
    # die API nicht mehr erreichbar, weil jeder Dokument-Endpunkt den Patienten
    # voraussetzt, und trotzdem auf der Platte. Zuerst der Patient, dann die
    # Akte — bricht es dazwischen ab, bleiben verwaiste Dateien statt eines
    # Patienten ohne seine Dokumente.
    removed_documents = documents_service.delete_for_patient(patient_id)

    # Nach dem Löschen protokolliert: Der Eintrag im Trail ist ab jetzt der
    # einzige Beleg, dass es diesen Patienten je gab.
    _audit(
        request,
        EventType.PATIENT_DELETED,
        None,
        status.HTTP_204_NO_CONTENT,
        patient_id=patient_id,
        documents_removed=removed_documents,
    )


def _audit(
    request: Request,
    event: EventType,
    patient: Patient | None,
    status_code: int,
    patient_id: int | None = None,
    **detail: object,
) -> None:
    """Hält eine Änderung an einem Patienten im Audit-Trail fest.

    Nur die Kennung, nie Name, Geburtsdatum oder Versichertennummer — der Trail
    liegt dauerhaft in einer eigenen Datenbank, siehe `audit/events.py`.
    """
    identifier = patient.id if patient is not None else patient_id
    audit.record(
        event,
        request=request,
        status=status_code,
        user_id=request.state.user_id,
        target=f"patient:{identifier}",
        detail=detail,
    )


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
