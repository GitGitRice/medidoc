"""Die Patienten-Logik — alles, was mit der Datenbank spricht.

Bewusst ohne FastAPI: keine `HTTPException`, keine `Depends`, keine
Statuscodes. Diese Datei weiß nicht, dass es HTTP gibt; der Router übersetzt
die Rückgaben in Antworten. Dadurch bleibt die Logik einzeln testbar und der
Router kurz genug, um ihn am Stück zu lesen.
"""

from sqlalchemy import ColumnElement, and_, func, or_
from sqlmodel import Session, col, select

from app.modules.patients.models import Patient
from app.modules.patients.schemas import PatientCreate, PatientUpdate

# Damit ein versehentliches `limit=100000` die Übersicht nicht lahmlegt.
MAX_LIMIT = 100


def search(
    session: Session,
    query: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[Patient], int]:
    """Patienten für die Übersicht, sortiert nach Nachname.

    Gibt den Ausschnitt und die Gesamttrefferzahl zurück — letztere ohne
    `limit`/`offset`, weil das Frontend daraus die Seitenzahl bildet.
    """
    limit = max(1, min(limit, MAX_LIMIT))
    offset = max(0, offset)

    condition = _match(query)

    rows = select(Patient)
    total = select(func.count()).select_from(Patient)
    if condition is not None:
        rows = rows.where(condition)
        total = total.where(condition)

    rows = (
        rows.order_by(col(Patient.last_name), col(Patient.first_name), col(Patient.id))
        .limit(limit)
        .offset(offset)
    )

    return list(session.exec(rows).all()), session.exec(total).one()


def get(session: Session, patient_id: int) -> Patient | None:
    """Ein Patient über die ID. `None`, wenn es ihn nicht gibt."""
    return session.get(Patient, patient_id)


def insurance_number_taken(
    session: Session, insurance_number: str, exclude_id: int | None = None
) -> bool:
    """Ob die Versichertennummer schon vergeben ist.

    `exclude_id` blendet den Patienten aus, der gerade bearbeitet wird —
    sonst kollidierte er beim Speichern mit sich selbst.
    """
    statement = select(Patient).where(Patient.insurance_number == insurance_number)
    if exclude_id is not None:
        statement = statement.where(col(Patient.id) != exclude_id)
    return session.exec(statement).first() is not None


def create(session: Session, data: PatientCreate) -> Patient:
    """Legt einen Patienten an und gibt ihn mit vergebener ID zurück."""
    patient = Patient(**data.model_dump())
    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient


def update(session: Session, patient: Patient, data: PatientUpdate) -> Patient:
    """Ändert die übergebenen Felder. Weggelassene bleiben, wie sie sind.

    `exclude_unset` ist hier der entscheidende Teil: Ohne das würden alle nicht
    geschickten Felder mit ihrem Default `None` überschrieben — ein PATCH mit
    einem Feld würde den Rest des Patienten leeren.
    """
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(patient, field, value)

    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient


def delete(session: Session, patient: Patient) -> None:
    """Entfernt den Patienten endgültig.

    Kein Soft-Delete: Löschen ist laut ADR-0005 die einzige Aktion, die Daten
    unwiederbringlich entfernt, und genau deshalb `admin` vorbehalten.
    """
    session.delete(patient)
    session.commit()


def _match(query: str | None) -> ColumnElement[bool] | None:
    """Baut die Suchbedingung. `None`, wenn nicht gesucht wird.

    Mehrere Wörter werden UND-verknüpft, jedes einzelne darf in Vor-, Nachname
    oder Versichertennummer treffen. "max muster" findet damit "Max
    Mustermann", "muster max" genauso.
    """
    if not query or not query.strip():
        return None

    conditions = []
    for term in query.split():
        # % und _ sind in LIKE Platzhalter. Ohne Maskierung würde die Suche
        # nach "%" jeden Patienten finden.
        escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        conditions.append(
            or_(
                col(Patient.first_name).ilike(pattern, escape="\\"),
                col(Patient.last_name).ilike(pattern, escape="\\"),
                col(Patient.insurance_number).ilike(pattern, escape="\\"),
            )
        )

    return and_(*conditions)
