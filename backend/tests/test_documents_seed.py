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
    """Die Patienten, an denen die Testdokumente hängen.

    Die Datei nennt sie über `patient_id`, und diese Kennung muss der `id` in
    der Datenbank entsprechen. Hier wird derselbe Zusammenhang hergestellt wie
    im echten Seed: Patienten der Reihe nach anlegen, bis die höchste in der
    Datei genannte Kennung vergeben ist.
    """
    highest = max(document.patient_id for document in load_documents())
    return {
        position: make_patient(
            first_name="Test",
            last_name=f"Patient {position}",
            insurance_number=f"T{position:09d}",
        )
        for position in range(1, highest + 1)
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

        assert any(d.attachments for d in documents)
        assert any(not d.attachments for d in documents)

    def test_es_gibt_ein_dokument_mit_mehreren_anhaengen(self):
        """Der Fall, für den die Änderung gemacht wurde — er muss vorkommen."""
        assert any(len(d.attachments) > 1 for d in load_documents())

    def test_die_patienten_kennungen_sind_ganze_zahlen_ab_eins(self):
        """Sie müssen den `id`-Werten aus Postgres entsprechen."""
        for document in load_documents():
            assert isinstance(document.patient_id, int)
            assert document.patient_id >= 1

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
        created = sum(
            documents.search(patient.id, None, 100, 0)[1]
            for patient in seed_patients.values()
        )
        assert created == expected

    def test_ein_zweiter_lauf_legt_nichts_doppelt_an(
        self, session, documents, seed_patients
    ):
        seed_documents(session)
        before = documents.search(1, None, 100, 0)[1]

        seed_documents(session)

        assert documents.search(1, None, 100, 0)[1] == before

    def test_ohne_passenden_patienten_wird_uebersprungen(self, session, documents):
        # Der Fall nach `--patients 3`: Die Datei nennt Patienten, die es in
        # dieser Datenbank nicht gibt. Das ist kein Fehler.
        seed_documents(session)

        assert documents.search(1, None, 100, 0)[1] == 0

    def test_die_anhaenge_liegen_wirklich_auf_der_platte(
        self, session, documents, seed_patients, upload_dir
    ):
        seed_documents(session)

        with_attachments = next(d for d in load_documents() if d.attachments)
        stored = documents.get(with_attachments.patient_id, with_attachments.id)

        assert len(stored["attachments"]) == len(with_attachments.attachments)
        for entry in stored["attachments"]:
            file = upload_dir / entry["stored_as"]
            assert file.exists()
            # Die Größe ist die des Platzhalters, nicht eine erfundene Zahl.
            assert file.stat().st_size == entry["size_bytes"] > 0

    def test_mehrere_anhaenge_liegen_als_eigene_dateien(
        self, session, documents, seed_patients, upload_dir
    ):
        seed_documents(session)

        several = next(d for d in load_documents() if len(d.attachments) > 1)
        stored = documents.get(several.patient_id, several.id)

        paths = {entry["stored_as"] for entry in stored["attachments"]}
        assert len(paths) == len(several.attachments)

    def test_die_herkunft_steht_am_anhang(
        self, session, documents, seed_patients
    ):
        seed_documents(session)

        with_source = next(
            d for d in load_documents() if any(a.source for a in d.attachments)
        )
        stored = documents.get(with_source.patient_id, with_source.id)

        assert any(entry["source"] for entry in stored["attachments"])

    def test_ein_dokument_ohne_anhang_faesst_die_platte_nicht_an(
        self, session, documents, seed_patients
    ):
        seed_documents(session)

        without = next(d for d in load_documents() if not d.attachments)

        assert documents.get(without.patient_id, without.id)["attachments"] == []

    def test_datum_und_kennung_kommen_aus_der_datei(
        self, session, documents, seed_patients
    ):
        # Feste Kennungen sind die Bedingung dafür, dass ein zweiter Lauf die
        # Dokumente wiedererkennt; feste Daten machen aus der Akte einen
        # Verlauf statt siebzehn Einträgen von heute.
        seed_documents(session)

        expected = load_documents()[0]
        stored = documents.get(expected.patient_id, expected.id)

        assert stored is not None
        assert stored["created_at"] == expected.created_at
