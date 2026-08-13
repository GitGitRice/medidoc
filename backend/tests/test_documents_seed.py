"""Die Testdokumente aus `testdata/documents.json`.

Ein Seed, der beim zweiten Lauf jede Akte verdoppelt, fällt erst auf, wenn
jemand ihn zweimal ausgeführt hat — und dann in der Oberfläche. Deshalb steht
er hier.

Läuft wie die übrigen Dokumenttests gegen den Speicher-Store und einen
`tmp_path`-Ordner — kein MongoDB, kein Docker (siehe conftest.py).

Die Testnamen sind deutsche Sätze, alles andere ist englisch — so schreibt es
backend/README.md vor.
"""

import pytest

from app.modules.documents.seed import load_documents, seed_documents

# Die vier Dokumenttypen aus docs/documents-api.md. Sie sind eine Verabredung
# und keine Liste im Code — die Testdaten sollen sie trotzdem alle zeigen,
# sonst sieht sich das Frontend immer nur einen Fall an.
USUAL_TYPES = {"befund", "arztbrief", "laborwert", "sonstiges"}


@pytest.fixture(name="seed_patients")
def seed_patients_fixture(make_patient):
    """Die Patienten, an denen die Testdokumente hängen — über ihre Nummer."""
    return {
        record.insurance_number: make_patient(
            first_name="Test",
            last_name=f"Patient {position}",
            insurance_number=record.insurance_number,
        )
        for position, record in enumerate(
            {d.insurance_number: d for d in load_documents()}.values(), start=1
        )
    }


class TestTestdaten:
    def test_jeder_datensatz_ist_gueltig(self):
        # `load_documents` schickt jeden Datensatz durch dieselbe Prüfung wie
        # ein echter POST. Ein kaputter Eintrag wirft hier, nicht erst beim Seed.
        assert len(load_documents()) > 0

    def test_alle_vier_ueblichen_dokumenttypen_kommen_vor(self):
        types = {d.metadata.document_type for d in load_documents()}

        assert USUAL_TYPES <= types

    def test_es_gibt_dokumente_mit_und_ohne_anhang(self):
        documents = load_documents()

        assert any(d.filename is not None for d in documents)
        assert any(d.filename is None for d in documents)

    def test_die_tags_sind_kleingeschrieben_und_ohne_dubletten(self):
        for document in load_documents():
            tags = document.metadata.tags
            assert tags == [t.lower() for t in tags]
            assert len(tags) == len(set(tags))

    def test_die_kennungen_sind_eindeutig(self):
        ids = [d.id for d in load_documents()]

        assert len(ids) == len(set(ids))


class TestAnlegen:
    def test_legt_die_dokumente_der_vorhandenen_patienten_an(
        self, session, documents, seed_patients
    ):
        seed_documents(session)

        expected = len(load_documents())
        angelegt = sum(
            documents.search(patient.id, None, 100, 0)[1]
            for patient in seed_patients.values()
        )
        assert angelegt == expected

    def test_ein_zweiter_lauf_legt_nichts_doppelt_an(
        self, session, documents, seed_patients
    ):
        seed_documents(session)
        vorher = documents.search(next(iter(seed_patients.values())).id, None, 100, 0)[1]

        seed_documents(session)

        nachher = documents.search(next(iter(seed_patients.values())).id, None, 100, 0)[1]
        assert nachher == vorher

    def test_ohne_passenden_patienten_wird_uebersprungen(self, session, documents):
        # Der Fall nach `--patients 3`: Die Datei nennt Patienten, die es in
        # dieser Datenbank nicht gibt. Das ist kein Fehler.
        seed_documents(session)

        assert documents.search(1, None, 100, 0)[1] == 0

    def test_der_anhang_liegt_wirklich_auf_der_platte(
        self, session, documents, seed_patients, upload_dir
    ):
        seed_documents(session)

        with_attachment = next(d for d in load_documents() if d.filename is not None)
        patient = seed_patients[with_attachment.insurance_number]

        stored = documents.get(patient.id, with_attachment.id)["attachment"]
        file = upload_dir / stored["stored_as"]

        assert file.exists()
        # Die Größe ist die des Platzhalters, nicht eine erfundene Zahl.
        assert file.stat().st_size == stored["size_bytes"] > 0
        assert stored["filename"] == with_attachment.filename

    def test_ein_dokument_ohne_anhang_faesst_die_platte_nicht_an(
        self, session, documents, seed_patients
    ):
        seed_documents(session)

        without = next(d for d in load_documents() if d.filename is None)
        patient = seed_patients[without.insurance_number]

        assert documents.get(patient.id, without.id)["attachment"] is None

    def test_datum_und_kennung_kommen_aus_der_datei(
        self, session, documents, seed_patients
    ):
        # Feste Kennungen sind die Bedingung dafür, dass ein zweiter Lauf die
        # Dokumente wiedererkennt; feste Daten machen aus der Akte einen
        # Verlauf statt siebzehn Einträgen von heute.
        seed_documents(session)

        expected = load_documents()[0]
        patient = seed_patients[expected.insurance_number]

        stored = documents.get(patient.id, expected.id)
        assert stored is not None
        assert stored["created_at"] == expected.created_at
