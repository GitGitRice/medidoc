"""Testpatienten aus `backend/testdata/patients.json`.

Frei erfunden — im ganzen Projekt werden ausschließlich Testdaten verwendet,
keine echten Patientendaten.

Die Daten stehen als JSON daneben und nicht als Python-Literal im Code: So kann
das Frontend dieselbe Datei als Mock benutzen, solange die Endpunkte noch nicht
stehen, und neue Fälle kommen dazu, ohne dass jemand Python anfasst. JSON statt
YAML, weil `json` in der Standardbibliothek liegt — YAML wäre eine zusätzliche
Abhängigkeit für nichts.
"""

import json
from pathlib import Path

from pydantic import ValidationError
from sqlmodel import Session, select

from app.modules.patients.models import Patient
from app.modules.patients.schemas import PatientCreate

# app/modules/patients/seed.py -> patients -> modules -> app -> backend
TESTDATA = Path(__file__).resolve().parents[3] / "testdata" / "patients.json"


def load_patients(limit: int | None = None) -> list[PatientCreate]:
    """Liest die Datei und prüft jeden Datensatz.

    Die Testdaten laufen durch dieselbe Prüfung wie ein echter `POST /patients`.
    Ein kaputter Datensatz fällt damit beim Seed auf und nicht erst, wenn das
    Frontend ihn anzeigt.
    """
    raw = json.loads(TESTDATA.read_text(encoding="utf-8"))
    if limit is not None:
        raw = raw[:limit]

    patients = []
    for position, record in enumerate(raw, start=1):
        try:
            patients.append(PatientCreate(**record))
        except ValidationError as error:
            raise ValueError(
                f"{TESTDATA.name}: Datensatz {position} ist ungültig — {error}"
            ) from error
    return patients


def seed_patients(session: Session, limit: int | None = None) -> None:
    """Legt die Testpatienten an. Vorhandene bleiben unangetastet.

    Erkannt werden sie an der Versichertennummer; Patienten ohne Nummer über
    Name und Geburtsdatum. Für Testdaten reicht das — als Identität im Betrieb
    wäre es untauglich, zwei echte Menschen dürfen so heißen.
    """
    known = session.exec(select(Patient)).all()
    known_numbers = {p.insurance_number for p in known if p.insurance_number}
    known_identities = {(p.first_name, p.last_name, p.date_of_birth) for p in known}

    created = 0
    skipped = 0

    for data in load_patients(limit):
        if data.insurance_number:
            duplicate = data.insurance_number in known_numbers
        else:
            duplicate = (
                data.first_name,
                data.last_name,
                data.date_of_birth,
            ) in known_identities

        if duplicate:
            skipped += 1
            continue

        session.add(Patient(**data.model_dump()))
        if data.insurance_number:
            known_numbers.add(data.insurance_number)
        known_identities.add((data.first_name, data.last_name, data.date_of_birth))
        created += 1

    print(f"patients  angelegt: {created}, schon vorhanden: {skipped}")
