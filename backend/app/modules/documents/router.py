"""Dokumente zu einem Patienten — Endpunkte.

| Methode | Pfad | |
| ------- | ---- | - |
| `POST` | `/patients/{patient_id}/documents` | Dokument anlegen, multipart |
| `GET` | `/patients/{patient_id}/documents?q=&limit=&offset=` | Dokumente auflisten |
| `GET` | `…/documents/{document_id}/attachments/{attachment_id}` | Anhang abrufen |
| `DELETE` | `…/documents/{document_id}` | Dokument löschen, nur `admin` |

Ein Dokument besteht aus Angaben und **beliebig vielen Anhängen** — auch keinem.
Angelegt wird deshalb auch ohne Anhang; `multipart` bleibt es trotzdem, weil
dieselbe Route auch den Fall mit Anhängen bedient.

Die Bytes eines Anhangs kommen über den eigenen Abruf-Endpunkt heraus, nie über
die Liste. Seine Adresse steht fertig in jeder Antwort (`attachments[].url`).

Alle verlangen einen angemeldeten Benutzer; die Prüfung hängt wie bei den
Patienten am Router und nicht an den einzelnen Funktionen, damit ein neu
dazukommender Endpunkt nicht versehentlich offen steht.

`DELETE` verlangt zusätzlich `admin`. [ADR-0005](../../../../docs/adr/0005-rollen-admin-und-staff.md)
gibt `staff` ausdrücklich „Dokumente lesen und anlegen" — Löschen steht dort
nicht, und es ist die Aktion, die Daten unwiederbringlich entfernt. Dieselbe
Linie wie beim Löschen eines Patienten.

**Zum Pfad:** Die Dokumente hängen unter dem Patienten, weil ein Dokument ohne
Patienten nicht existiert — der Pfad sagt dasselbe wie das Datenmodell. Der
frühere `/docs/{patient_id}` tat das nicht und lag außerdem auf demselben
Anfang wie FastAPIs eigene Swagger-Oberfläche unter `/docs`. Beides ist damit
erledigt.
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
from fastapi.responses import FileResponse
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
    MAX_ATTACHMENTS,
    parse_tags,
)
from app.modules.documents.storage import EmptyFile, FileTooLarge
from app.modules.patients import service as patients_service
from app.modules.users.models import Role, User

router = APIRouter(
    prefix="/patients/{patient_id}/documents",
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
    "",
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
    files: Annotated[
        list[UploadFile],
        File(description="Die Anhänge — beliebig viele, je höchstens 20 MB"),
    ] = [],
    source: Annotated[
        list[str],
        Form(
            description=(
                "Herkunft je Anhang, in derselben Reihenfolge wie \"files\". "
                "Ein einzelner Wert gilt für alle."
            )
        ),
    ] = [],
) -> DocumentPublic:
    """Legt ein Dokument in der Akte eines Patienten an.

    **Multipart**, nicht JSON — anders reisen Anhänge nicht. `tags` kommt
    kommagetrennt herein und geht als Liste wieder hinaus.

    **Anhänge sind optional und dürfen mehrere sein.** Ohne `files` entsteht
    ein Dokument ohne Anhang; jeder mitgeschickte muss etwas enthalten — ein
    leerer Anhang ist ein Versehen und ergibt `422`.

    `source` wird den Anhängen der Reihe nach zugeordnet. Ein einzelner Wert
    gilt für alle — der übliche Fall, dass ein dreiseitiger Scan komplett aus
    derselben Praxis kommt.

    Über 20 MB je Anhang antwortet die API mit `413`. Geprüft wird beim
    Schreiben und nicht danach, damit ein großer Anhang nicht erst vollständig
    im Speicher landet. Kippt ein späterer Anhang, bleibt auch von den früheren
    nichts liegen.
    """
    _patient_or_404(session, patient_id)

    metadata = _metadata(document_type, title, description, tags)
    attachments = _incoming_attachments(files, source)

    try:
        document = service.create(
            patient_id=patient_id,
            metadata=metadata,
            attachments=attachments,
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
            "attachments": len(document.attachments),
            "size_bytes": sum(a.size_bytes for a in document.attachments),
        },
    )

    return document


@router.get(
    "",
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


@router.get(
    "/{document_id}/attachments/{attachment_id}",
    summary="Anhang abrufen",
    response_class=FileResponse,
    responses={
        200: {
            "content": {"application/octet-stream": {}},
            "description": "Die Bytes des Anhangs",
        },
        401: UNAUTHORIZED,
        404: NOT_FOUND,
    },
)
def get_attachment(
    session: SessionDep,
    patient_id: int,
    document_id: str,
    attachment_id: str,
    download: Annotated[
        bool,
        Query(
            description=(
                "true erzwingt den Speichern-Dialog, sonst wird der Anhang "
                "zum Ansehen ausgeliefert"
            )
        ),
    ] = False,
) -> FileResponse:
    """Liefert die Bytes eines Anhangs aus.

    Die Adresse steht fertig in jeder Dokumentantwort unter
    `attachments[].url` — das Frontend muss sie nicht selbst zusammensetzen.

    Alle drei Kennungen müssen zusammenpassen. Wer die Kennung eines fremden
    Anhangs errät, bekommt ihn nicht über den eigenen Patienten: Passt eine
    nicht, ist die Antwort `404` — dieselbe wie für „gibt es nicht", damit sie
    nicht verrät, welcher Teil gestimmt hätte.

    Standard ist `Content-Disposition: inline` — ein PDF oder ein Scan soll
    sich im Browser ansehen lassen, ohne erst gespeichert zu werden. Mit
    `?download=true` wird daraus `attachment`, und der Browser öffnet den
    Speichern-Dialog. Der Dateiname steht in beiden Fällen dabei.

    Beide Adressen stehen fertig in der Dokumentantwort: `attachments[].url`
    für die Vorschau, `attachments[].download_url` für den Download.
    """
    _patient_or_404(session, patient_id)

    attachment = service.open_attachment(patient_id, document_id, attachment_id)
    if attachment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Anhang {attachment_id} wurde für dieses Dokument nicht gefunden",
        )

    return FileResponse(
        attachment.path,
        media_type=attachment.content_type,
        filename=attachment.filename,
        content_disposition_type="attachment" if download else "inline",
    )


@router.delete(
    "/{document_id}",
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


def _incoming_attachments(
    files: list[UploadFile], sources: list[str]
) -> list[service.IncomingAttachment]:
    """Bündelt Dateien und Herkunftsangaben zu je einem Anhang.

    Die beiden Listen kommen aus dem Formular getrennt herein und werden hier
    der Reihe nach gepaart. Ein einzelner `source` gilt für alle Anhänge — der
    übliche Fall, dass ein dreiseitiger Scan komplett aus derselben Praxis
    stammt. Fehlen Angaben, bleiben die übrigen Anhänge ohne Herkunft; das ist
    kein Fehler, `source` ist optional.

    Ein Formularfeld `files` ohne Datei schickt der Browser als leeren Teil mit.
    Der wird hier aussortiert, sonst entstünde daraus ein leerer Anhang und
    damit ein `422` für ein Dokument, das gar keinen tragen sollte.
    """
    uploads = [
        upload
        for upload in files
        if upload is not None and (upload.filename or upload.size)
    ]

    if len(uploads) > MAX_ATTACHMENTS:
        raise RequestValidationError(
            [
                {
                    "type": "too_long",
                    "loc": ("body", "files"),
                    "msg": f"höchstens {MAX_ATTACHMENTS} Anhänge",
                    "input": len(uploads),
                }
            ]
        )

    given = [value.strip() for value in sources]

    def source_for(position: int) -> str | None:
        if len(given) == 1:
            return given[0] or None
        if position < len(given):
            return given[position] or None
        return None

    return [
        service.IncomingAttachment(
            stream=upload.file,
            filename=upload.filename,
            content_type=upload.content_type,
            source=source_for(position),
        )
        for position, upload in enumerate(uploads)
    ]


def _metadata(
    document_type: str,
    title: str,
    description: str | None,
    tags: str | None,
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
