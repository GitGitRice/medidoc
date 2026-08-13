"""Dokumente zu einem Patienten — Endpunkte.

| Methode | Pfad | |
| ------- | ---- | - |
| `POST` | `/docs/{patient_id}` | Dokument anlegen, multipart |
| `GET` | `/docs/{patient_id}?q=&limit=&offset=` | Dokumente auflisten |
| `PATCH` | `/docs/{patient_id}/{document_id}` | Angaben ändern, JSON |
| `DELETE` | `/docs/{patient_id}/{document_id}` | Dokument löschen, nur `admin` |

Ein Dokument besteht aus Angaben und **optional** einem Anhang (CONTEXT.md).
Angelegt wird deshalb auch ohne Anhang — `multipart` bleibt es trotzdem, weil
dieselbe Route auch den Fall mit Anhang bedient.

Alle verlangen einen angemeldeten Benutzer; die Prüfung hängt wie bei den
Patienten am Router und nicht an den einzelnen Funktionen, damit ein neu
dazukommender Endpunkt nicht versehentlich offen steht.

`DELETE` verlangt zusätzlich `admin`. [ADR-0005](../../../../docs/adr/0005-rollen-admin-und-staff.md)
gibt `staff` ausdrücklich „Dokumente lesen und anlegen" — Löschen steht dort
nicht, und es ist die Aktion, die Daten unwiederbringlich entfernt. Dieselbe
Linie wie beim Löschen eines Patienten.

**Zum Pfad `/docs`:** Er ist so vorgegeben. FastAPI liefert unter `/docs` seine
eigene Swagger-Oberfläche aus — die bleibt erreichbar, weil sie auf dem exakten
Pfad `/docs` liegt und hier erst `/docs/{patient_id}` beginnt. Verwechslungsfrei
ist es trotzdem nicht, und der übrige Bestand heißt `/patients`. Ein Zug nach
`/patients/{id}/documents` wäre naheliegend — siehe docs/documents-api.md.
"""

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlmodel import Session

from app.core.errors import ErrorResponse
from app.db.session import get_session
from app.modules.audit import service as audit
from app.modules.audit.events import EventType
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.documents import service
from app.modules.documents.schemas import (
    DocumentMetadata,
    DocumentPage,
    DocumentPublic,
    DocumentUpdate,
    parse_tags,
)
from app.modules.documents.storage import EmptyFile, FileTooLarge
from app.modules.patients import service as patients_service
from app.modules.users.models import Role, User

router = APIRouter(
    prefix="/docs",
    tags=["documents"],
    dependencies=[Depends(get_current_user)],
)

SessionDep = Annotated[Session, Depends(get_session)]
AdminUser = Annotated[User, Depends(require_roles(Role.ADMIN))]

UNAUTHORIZED = {"model": ErrorResponse, "description": "Nicht angemeldet"}
FORBIDDEN = {"model": ErrorResponse, "description": "Rolle reicht nicht"}
NOT_FOUND = {"model": ErrorResponse, "description": "Patient oder Dokument nicht gefunden"}
TOO_LARGE = {"model": ErrorResponse, "description": "Anhang zu groß"}
UNPROCESSABLE = {"model": ErrorResponse, "description": "Eingabe ungültig"}


@router.post(
    "/{patient_id}",
    response_model=DocumentPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Dokument anlegen",
    responses={
        401: UNAUTHORIZED,
        404: NOT_FOUND,
        413: TOO_LARGE,
        422: UNPROCESSABLE,
    },
)
def create_document(
    request: Request,
    session: SessionDep,
    patient_id: int,
    document_type: Annotated[
        str, Form(description="Dokumenttyp, z. B. \"befund\" oder \"laborwert\"")
    ],
    title: Annotated[str, Form(description="Titel des Dokuments")],
    description: Annotated[str | None, Form()] = None,
    tags: Annotated[
        str | None, Form(description="Kommagetrennt, z. B. \"mrt, radiologie\"")
    ] = None,
    source: Annotated[
        str | None, Form(description="Woher das Dokument stammt, z. B. \"Radiologie Mitte\"")
    ] = None,
    fields: Annotated[
        str | None,
        Form(
            description=(
                "Die typabhängigen Angaben als JSON-Objekt, "
                "z. B. {\"hb\": 13.4, \"einheit\": \"g/dl\"}"
            )
        ),
    ] = None,
    file: Annotated[
        UploadFile | None,
        File(description="Der Anhang — optional, höchstens 20 MB"),
    ] = None,
) -> DocumentPublic:
    """Legt ein Dokument in der Akte eines Patienten an.

    **Multipart**, nicht JSON — anders reist ein Anhang nicht. `tags` kommt
    kommagetrennt herein und geht als Liste wieder hinaus, `fields` als
    JSON-Objekt.

    **Der Anhang ist optional** (CONTEXT.md: „ein Dokument ohne Anhang ist
    gültig"). Wird das Feld `file` weggelassen, entsteht ein Dokument ohne
    Anhang; wird es mitgeschickt, muss etwas drin sein — ein leerer Anhang ist
    ein Versehen und ergibt `422`.

    Über 20 MB antwortet die API mit `413`. Geprüft wird beim Schreiben und
    nicht danach, damit ein großer Anhang nicht erst vollständig im Speicher
    landet.
    """
    _patient_or_404(session, patient_id)

    metadata = _metadata(document_type, title, description, tags, source, fields)

    try:
        document = service.create(
            patient_id=patient_id,
            metadata=metadata,
            stream=file.file if file is not None else None,
            filename=file.filename if file is not None else None,
            content_type=file.content_type if file is not None else None,
            created_by=request.state.user_id,
        )
    except FileTooLarge as too_large:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=(
                f"Der Anhang ist größer als {_megabytes(too_large.limit_bytes)} MB "
                "und wurde nicht gespeichert"
            ),
        ) from None
    except EmptyFile:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Der Anhang ist leer",
        ) from None

    audit.record(
        EventType.DOCUMENT_CREATED,
        request=request,
        status=status.HTTP_201_CREATED,
        user_id=request.state.user_id,
        target=f"document:{document.id}",
        # Kein Dateiname und kein Titel — beide tragen in der Praxis
        # Patientennamen. Der Dokumenttyp ist dagegen eine feste Fachkategorie
        # und verrät nichts über den Patienten; Größe und Typ sagen genug, um
        # einen Vorfall einzuordnen.
        detail={
            "patient": f"patient:{patient_id}",
            "document_type": document.document_type,
            "size_bytes": (
                document.attachment.size_bytes if document.attachment else None
            ),
            "content_type": (
                document.attachment.content_type if document.attachment else None
            ),
        },
    )

    return document


@router.get(
    "/{patient_id}",
    response_model=DocumentPage,
    summary="Dokumente eines Patienten",
    responses={401: UNAUTHORIZED, 404: NOT_FOUND, 422: UNPROCESSABLE},
)
def list_documents(
    session: SessionDep,
    patient_id: int,
    q: Annotated[
        str | None,
        Query(description="Filtert nach Titel oder Beschreibung, Schreibweise egal"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=service.MAX_LIMIT)] = service.MAX_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DocumentPage:
    """Alle Dokumente eines Patienten, neueste zuerst.

    Findet `q` nichts, ist `items` eine leere Liste und `total` gleich null —
    das ist **kein** Fehler.
    """
    _patient_or_404(session, patient_id)

    items, total = service.search(patient_id, q=q, limit=limit, offset=offset)
    return DocumentPage(items=items, total=total, limit=limit, offset=offset)


@router.patch(
    "/{patient_id}/{document_id}",
    response_model=DocumentPublic,
    summary="Angaben eines Dokuments ändern",
    responses={401: UNAUTHORIZED, 404: NOT_FOUND, 422: UNPROCESSABLE},
)
def update_document(
    request: Request,
    session: SessionDep,
    patient_id: int,
    document_id: str,
    data: DocumentUpdate,
) -> DocumentPublic:
    """Ändert nur die mitgeschickten Angaben und gibt das ganze Dokument zurück.

    **JSON, nicht multipart** — anders als beim Anlegen reist hier kein Anhang
    mit, und für reine Angaben ist JSON die natürliche Form.

    Weggelassene Felder bleiben unverändert. `document_type` und `title` dürfen
    weggelassen, aber nicht geleert werden; `description` und `source` lassen
    sich mit `null` oder `""` leeren. `fields` **ersetzt** die typabhängigen
    Angaben vollständig — sonst liesse sich ein Schlüssel nie wieder entfernen.

    Nicht änderbar sind der Patient und der Anhang: Ein Dokument einem anderen
    Patienten zuzuordnen ist keine Korrektur, und ein Anhang reist nicht durch
    JSON.

    `staff` darf ändern — dieselbe Linie wie beim Bearbeiten eines Patienten
    (ADR-0005). Nur das Löschen bleibt `admin` vorbehalten.
    """
    _patient_or_404(session, patient_id)

    document = service.update(patient_id, document_id, data)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dokument {document_id} wurde für diesen Patienten nicht gefunden",
        )

    audit.record(
        EventType.DOCUMENT_UPDATED,
        request=request,
        status=status.HTTP_200_OK,
        user_id=request.state.user_id,
        target=f"document:{document_id}",
        # Welche Felder angefasst wurden, nicht womit sie gefüllt wurden — im
        # Titel und in `fields` stehen in der Praxis Patientenangaben.
        detail={
            "patient": f"patient:{patient_id}",
            "fields": sorted(data.model_dump(exclude_unset=True)),
        },
    )

    return document


@router.delete(
    "/{patient_id}/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Dokument löschen",
    responses={401: UNAUTHORIZED, 403: FORBIDDEN, 404: NOT_FOUND},
)
def delete_document(
    request: Request,
    session: SessionDep,
    _admin: AdminUser,
    patient_id: int,
    document_id: str,
) -> None:
    """Löscht Angaben und Anhang endgültig — nur als `admin`.

    Zweimaliges Löschen ist kein Serverfehler: Der zweite Aufruf findet das
    Dokument nicht mehr und antwortet mit `404`.
    """
    _patient_or_404(session, patient_id)

    if not service.delete(patient_id, document_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dokument {document_id} wurde für diesen Patienten nicht gefunden",
        )

    audit.record(
        EventType.DOCUMENT_DELETED,
        request=request,
        status=status.HTTP_204_NO_CONTENT,
        user_id=request.state.user_id,
        target=f"document:{document_id}",
        detail={"patient": f"patient:{patient_id}"},
    )


def _metadata(
    document_type: str,
    title: str,
    description: str | None,
    tags: str | None,
    source: str | None,
    fields: str | None,
) -> DocumentMetadata:
    """Baut die geprüften Angaben — und macht aus einem Fehler ein `422`.

    Ein `ValidationError`, der beim Bauen eines Models *im Router* entsteht,
    ist für FastAPI ein gewöhnlicher Programmfehler und würde `500`. Umgemünzt
    auf `RequestValidationError` läuft er durch denselben Handler wie jede
    andere ungültige Eingabe und kommt im gewohnten Format heraus — mit
    Feldnamen in `errors`.
    """
    try:
        return DocumentMetadata(
            document_type=document_type,
            title=title,
            description=description,
            tags=parse_tags(tags),
            source=source,
            fields=fields,
        )
    except ValidationError as invalid:
        # `("title",)` wird zu `("body", "title")`, damit der Feldname in der
        # Antwort genauso heißt wie das Formularfeld.
        errors = [
            {**error, "loc": ("body", *error.get("loc", ()))}
            for error in invalid.errors()
        ]
        raise RequestValidationError(errors) from None


def _patient_or_404(session: Session, patient_id: int) -> None:
    """Dokumente hängen immer an einem Patienten, den es gibt.

    Ohne diese Prüfung ließen sich Anhänge unter einer beliebigen Zahl ablegen —
    sie wären über die Liste nie wieder zu sehen und lägen trotzdem auf der
    Platte.
    """
    if patients_service.get(session, patient_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            # Der Satz kommt aus `patients` — derselbe Fehler soll überall
            # gleich heißen, egal über welche Route er auffällt.
            detail=patients_service.not_found_message(patient_id),
        )


def _megabytes(bytes_: int) -> int:
    return bytes_ // (1024 * 1024)
