"""Testdaten anlegen.

Aufruf aus `backend/`:

    python -m app.seed                 alle Testpatienten aus testdata/
    python -m app.seed --patients 50   nur die ersten 50

Mehrfach ausführbar — Vorhandenes wird übersprungen, nicht überschrieben.
Diese Datei ruft nur die Seeds der Module auf; die Daten selbst stehen jeweils
im Modul, dem sie gehören. Ein neues Modul mit Testdaten kommt mit einer Zeile
in `seed()` dazu.
"""

import argparse

from sqlmodel import Session

from app.db.base import init_db
from app.db.session import engine
from app.modules.patients.seed import seed_patients
from app.modules.users.seed import seed_users


def seed(patient_limit: int | None = None) -> None:
    init_db()

    # Eine Session und ein Commit für alle Module: Bricht ein Seed ab, bleibt
    # die Datenbank im Zustand von vorher statt halb gefüllt.
    with Session(engine) as session:
        seed_users(session)
        seed_patients(session, limit=patient_limit)
        session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Testdaten anlegen.")
    parser.add_argument(
        "--patients",
        type=int,
        default=None,
        metavar="N",
        help="nur die ersten N Testpatienten anlegen (Standard: alle)",
    )
    seed(patient_limit=parser.parse_args().patients)


if __name__ == "__main__":
    main()
