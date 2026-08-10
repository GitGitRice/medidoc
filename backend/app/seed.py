"""Testdaten anlegen.

Aufruf aus `backend/`:

    python -m app.seed                 alle Testpatienten und ihre Dokumente
    python -m app.seed --patients 50   nur die ersten 50 Patienten
    python -m app.seed --no-documents  ohne Dokumente, also ohne MongoDB

Mehrfach ausführbar — Vorhandenes wird übersprungen, nicht überschrieben.
Diese Datei ruft nur die Seeds der Module auf; die Daten selbst stehen jeweils
im Modul, dem sie gehören. Ein neues Modul mit Testdaten kommt mit einer Zeile
in `seed()` dazu.
"""

import argparse

from sqlmodel import Session

from app.db.base import init_db
from app.db.session import engine
from app.modules.documents.seed import seed_documents
from app.modules.patients.seed import seed_patients
from app.modules.users.seed import seed_users


def seed(patient_limit: int | None = None, with_documents: bool = True) -> None:
    init_db()

    # Eine Session und ein Commit für alles, was in Postgres landet: Bricht ein
    # Seed ab, bleibt die Datenbank im Zustand von vorher statt halb gefüllt.
    with Session(engine) as session:
        seed_users(session)
        seed_patients(session, limit=patient_limit)
        session.commit()

        # Erst nach dem Commit: Die Dokumente hängen an der `id` eines
        # Patienten, und die gibt es erst, wenn er wirklich in der Datenbank
        # steht. Sie liegen ohnehin woanders — in MongoDB, nicht in dieser
        # Session (ADR-0002).
        if with_documents:
            seed_documents(session)


def main() -> None:
    parser = argparse.ArgumentParser(description="Testdaten anlegen.")
    parser.add_argument(
        "--patients",
        type=int,
        default=None,
        metavar="N",
        help="nur die ersten N Testpatienten anlegen (Standard: alle)",
    )
    parser.add_argument(
        "--no-documents",
        action="store_true",
        help="keine Testdokumente anlegen (Standard: mit)",
    )
    arguments = parser.parse_args()
    seed(patient_limit=arguments.patients, with_documents=not arguments.no_documents)


if __name__ == "__main__":
    main()
