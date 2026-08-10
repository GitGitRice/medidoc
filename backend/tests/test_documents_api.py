"""Dokumente zu einem Patienten — ein Test pro Akzeptanzkriterium.

Der Vertrag steht in docs/documents-api.md. Gegliedert nach Endpunkt, dazu die
beiden Blöcke, die am meisten wehtun, wenn sie fehlen: die Größenprüfung eines
Anhangs und die Ablage auf der Platte.

Ein **Dokument** besteht aus beschreibenden Angaben und **beliebig vielen
Anhängen** — keinem, einem oder mehreren. Alle drei Fälle sind hier abgedeckt,
und die Bytes eines Anhangs kommen über einen eigenen Endpunkt wieder heraus.

Läuft gegen den Speicher-Store und einen `tmp_path`-Ordner — kein MongoDB, kein
Docker (siehe `documents`-Fixture in conftest.py).

Die Testnamen sind deutsche Sätze, alles andere ist englisch — so schreibt es
backend/README.md vor.
"""

import io

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.modules.audit.events import EventType
from app.modules.documents import service as documents_service
from app.modules.documents import storage as documents_storage
from app.modules.documents import store as documents_store
from app.modules.documents.schemas import (
    MAX_ATTACHMENTS,
    DocumentMetadata,
    parse_tags,
)
from app.modules.documents.storage import safe_suffix
from app.modules.documents.store import (
    SEARCHED_FIELDS,
    _search_filter,
    matches_term,
    normalize_term,
)


def docs_url(patient_id) -> str:
    """Die Dokumente eines Patienten hängen unter dem Patienten.

    An einer Stelle gebaut: Das Pfadschema ist einmal gewandert, und ein
    zweites Mal soll es nicht 43 Zeilen kosten.
    """
    return f"/patients/{patient_id}/documents"


def attachment(
    content: bytes = b"%PDF-1.4 Testinhalt",
    name: str | None = "befund.pdf",
    content_type: str = "application/pdf",
):
    """Ein Anhang, wie ihn ein Formular schickt.

    Als Liste von Paaren und nicht als Dict: Nur so lässt sich das Feld `files`
    mehrfach besetzen, und genau das ist seit dem Umstieg auf mehrere Anhänge
    der Normalfall.
    """
    return [("files", (name, io.BytesIO(content), content_type))]


def attachments(*parts):
    """Mehrere Anhänge für einen Request."""
    return [entry for part in parts for entry in part]


def create(
    client: TestClient,
    headers,
    patient_id: int,
    without_attachment: bool = False,
    **form,
):
    """Ein Dokument, wie es das Formular im Frontend schickt.

    `files` muss vor dem Zusammenbauen heraus — sonst landete der Anhang als
    Formularfeld in `data`. `without_attachment=True` lässt das Feld ganz weg;
    das ist der Fall, den CONTEXT.md ausdrücklich erlaubt.
    """
    files = form.pop("files", None) or attachment()
    data = {"document_type": "befund", "title": "Befund MRT"} | form
    return client.post(
        docs_url(patient_id),
        files=None if without_attachment else files,
        data=data,
        headers=headers,
    )


class TestAnlegen:
    """POST /patients/{patient_id}/documents"""

    def test_legt_das_dokument_an_und_liefert_201(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()

        response = create(client, admin_headers, patient.id)

        assert response.status_code == 201
        body = response.json()
        assert body["title"] == "Befund MRT"
        assert body["patient_id"] == patient.id
        assert body["id"]

    def test_uebernimmt_alle_angaben(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()

        body = create(
            client,
            admin_headers,
            patient.id,
            document_type="laborwert",
            title="Laborwerte Januar",
            description="Grosses Blutbild",
            tags="labor, blutbild",
            source="Labor Berlin",
        ).json()

        assert body["document_type"] == "laborwert"
        assert body["title"] == "Laborwerte Januar"
        assert body["description"] == "Grosses Blutbild"
        assert body["tags"] == ["labor", "blutbild"]
        assert body["attachments"][0]["source"] == "Labor Berlin"
        assert body["created_at"]

    def test_liefert_die_angaben_zum_anhang_mit(
        self, client: TestClient, admin_headers, make_patient
    ):
        """Ohne Name und Größe wäre die Liste im Frontend nicht bedienbar."""
        patient = make_patient()

        body = create(client, admin_headers, patient.id).json()

        assert body["attachments"][0]["filename"] == "befund.pdf"
        assert body["attachments"][0]["content_type"] == "application/pdf"
        assert body["attachments"][0]["size_bytes"] == len(b"%PDF-1.4 Testinhalt")

    def test_nur_typ_und_titel_reichen(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()

        body = create(client, admin_headers, patient.id).json()

        assert body["description"] is None
        assert body["attachments"][0]["source"] is None
        assert body["tags"] == []

    def test_fehlender_titel_liefert_422(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()

        response = client.post(
            docs_url(patient.id),
            files=attachment(),
            data={"document_type": "befund"},
            headers=admin_headers,
        )

        assert response.status_code == 422
        assert response.json()["message"] == "Pflichtfeld fehlt: title"

    def test_leerer_titel_liefert_422(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()

        response = create(client, admin_headers, patient.id, title="   ")

        assert response.status_code == 422

    def test_unbekannter_patient_liefert_404(self, client: TestClient, admin_headers):
        response = create(client, admin_headers, 999999)

        assert response.status_code == 404
        assert response.json()["message"] == "Patient mit der ID 999999 wurde nicht gefunden"

    def test_staff_darf_anlegen(
        self, client: TestClient, staff_headers, make_patient
    ):
        """ADR-0005: `staff` darf Dokumente lesen und anlegen."""
        patient = make_patient()

        assert create(client, staff_headers, patient.id).status_code == 201

    def test_ohne_token_wird_nichts_angelegt(
        self, client: TestClient, make_patient
    ):
        patient = make_patient()

        response = client.post(
            docs_url(patient.id),
            files=attachment(),
            data={"document_type": "befund", "title": "X"},
        )

        assert response.status_code == 401


class TestDokumenttyp:
    """Der Dokumenttyp ist ein Schlagwort — er bestimmt (noch) keine Felder."""

    def test_fehlender_dokumenttyp_liefert_422(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()

        response = client.post(
            docs_url(patient.id),
            files=attachment(),
            data={"title": "Ohne Typ"},
            headers=admin_headers,
        )

        assert response.status_code == 422
        assert response.json()["message"] == "Pflichtfeld fehlt: document_type"

    def test_leerer_dokumenttyp_liefert_422(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()

        response = create(client, admin_headers, patient.id, document_type="   ")

        assert response.status_code == 422

    @pytest.mark.parametrize("given", ["Befund", "BEFUND", "  befund  "])
    def test_der_dokumenttyp_wird_vereinheitlicht(
        self, client: TestClient, admin_headers, make_patient, given
    ):
        """Sonst wären `Befund` und `befund` zwei Typen."""
        patient = make_patient()

        body = create(client, admin_headers, patient.id, document_type=given).json()

        assert body["document_type"] == "befund"

    def test_ein_neuer_dokumenttyp_braucht_keine_codeaenderung(
        self, client: TestClient, admin_headers, make_patient
    ):
        """CONTEXT.md verlangt neue Typen ohne Schemaänderung — also keine Liste."""
        patient = make_patient()

        response = create(
            client, admin_headers, patient.id, document_type="impfausweis"
        )

        assert response.status_code == 201
        assert response.json()["document_type"] == "impfausweis"


class TestOhneAnhang:
    """CONTEXT.md: Ein Dokument ohne Anhang ist gültig."""

    def test_ein_dokument_ohne_anhang_wird_angelegt(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()

        response = create(client, admin_headers, patient.id, without_attachment=True)

        assert response.status_code == 201
        assert response.json()["attachments"] == []

    def test_es_bleibt_nichts_auf_der_platte(
        self, client: TestClient, admin_headers, make_patient, upload_dir
    ):
        """Ohne Anhang wird die Platte gar nicht erst angefasst."""
        patient = make_patient()

        create(client, admin_headers, patient.id, without_attachment=True)

        assert not upload_dir.exists() or [
            p for p in upload_dir.rglob("*") if p.is_file()
        ] == []

    def test_es_steht_in_der_liste(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()
        create(client, admin_headers, patient.id, without_attachment=True)

        body = client.get(docs_url(patient.id), headers=admin_headers).json()

        assert body["total"] == 1
        assert body["items"][0]["attachments"] == []

    def test_es_laesst_sich_loeschen(
        self, client: TestClient, admin_headers, make_patient
    ):
        """Beim Löschen darf kein Speicherort erwartet werden, den es nicht gibt."""
        patient = make_patient()
        document = create(
            client, admin_headers, patient.id, without_attachment=True
        ).json()

        response = client.delete(
            f"{docs_url(patient.id)}/{document['id']}", headers=admin_headers
        )

        assert response.status_code == 204

    def test_ein_mitgeschickter_leerer_anhang_ist_trotzdem_ein_fehler(
        self, client: TestClient, admin_headers, make_patient
    ):
        """„Kein Anhang" heisst Feld weglassen, nicht Feld leer schicken."""
        patient = make_patient()

        response = create(
            client, admin_headers, patient.id, files=attachment(content=b"")
        )

        assert response.status_code == 422
        assert response.json()["message"] == "Der Anhang ist leer"


class TestAnhangGroesse:
    """Die ausdrückliche Anforderung: höchstens 20 MB."""

    def test_die_grenze_liegt_bei_20_mb(self):
        assert settings.max_upload_bytes == 20 * 1024 * 1024

    def test_knapp_unter_der_grenze_wird_angenommen(
        self, client: TestClient, admin_headers, make_patient, monkeypatch
    ):
        # Die Grenze wird heruntergedreht, statt 20 MB durch den Test zu
        # schieben — geprüft wird die Regel, nicht die Geduld.
        monkeypatch.setattr(settings, "max_upload_bytes", 1024)
        patient = make_patient()

        response = create(
            client, admin_headers, patient.id, files=attachment(b"x" * 1024)
        )

        assert response.status_code == 201
        assert response.json()["attachments"][0]["size_bytes"] == 1024

    def test_ueber_der_grenze_liefert_413(
        self, client: TestClient, admin_headers, make_patient, monkeypatch
    ):
        monkeypatch.setattr(settings, "max_upload_bytes", 1024)
        patient = make_patient()

        response = create(
            client, admin_headers, patient.id, files=attachment(b"x" * 1025)
        )

        assert response.status_code == 413
        assert response.json()["status"] == 413
        assert "MB" in response.json()["message"]

    def test_ein_zu_grosser_anhang_legt_kein_dokument_an(
        self, client: TestClient, admin_headers, make_patient, monkeypatch
    ):
        """Kein halbes Dokument in der Liste."""
        monkeypatch.setattr(settings, "max_upload_bytes", 1024)
        patient = make_patient()

        create(client, admin_headers, patient.id, files=attachment(b"x" * 5000))

        assert (
            client.get(docs_url(patient.id), headers=admin_headers).json()["total"]
            == 0
        )

    def test_ein_zu_grosser_anhang_laesst_nichts_auf_der_platte(
        self, client: TestClient, admin_headers, make_patient, upload_dir, monkeypatch
    ):
        """Auch keine angefangene `.part`-Datei."""
        monkeypatch.setattr(settings, "max_upload_bytes", 1024)
        patient = make_patient()

        create(client, admin_headers, patient.id, files=attachment(b"x" * 5000))

        assert [p for p in upload_dir.rglob("*") if p.is_file()] == []


class TestAblage:
    """Was auf der Platte passiert."""

    def test_der_anhang_liegt_wirklich_da(
        self, client: TestClient, admin_headers, make_patient, upload_dir
    ):
        patient = make_patient()
        content = b"%PDF-1.4 echter Inhalt"

        response = create(
            client, admin_headers, patient.id, files=attachment(content)
        )

        document = response.json()
        found = list((upload_dir / str(patient.id) / document["id"]).glob("*"))
        assert len(found) == 1
        assert found[0].read_bytes() == content
        # Ein Ordner je Dokument, darin eine Datei je Anhang.
        assert document["attachments"][0]["id"] in found[0].name

    def test_jeder_patient_bekommt_einen_eigenen_ordner(
        self, client: TestClient, admin_headers, make_patient, upload_dir
    ):
        one = make_patient(first_name="Max")
        other = make_patient(first_name="Erika")

        create(client, admin_headers, one.id)
        create(client, admin_headers, other.id)

        assert {p.name for p in upload_dir.iterdir()} == {str(one.id), str(other.id)}

    def test_der_dateiname_des_aufrufers_wird_nie_zum_pfad(
        self, client: TestClient, admin_headers, make_patient, upload_dir
    ):
        """Der wichtigste Test dieser Datei.

        `../../` im Dateinamen darf nicht dazu führen, dass irgendetwas
        außerhalb des Ablage-Ordners landet.
        """
        patient = make_patient()

        response = create(
            client,
            admin_headers,
            patient.id,
            files=attachment(b"boese", name="../../../etc/passwd"),
        )

        assert response.status_code == 201
        document = response.json()
        written = [p for p in upload_dir.rglob("*") if p.is_file()]
        assert len(written) == 1
        # Die Datei liegt im Ordner des Dokuments, ihr Name ist die Kennung
        # des Anhangs — vom Namen des Aufrufers bleibt nichts übrig.
        assert written[0].parent == upload_dir / str(patient.id) / document["id"]
        assert document["attachments"][0]["id"] in written[0].name

    def test_der_urspruengliche_name_bleibt_als_angabe_erhalten(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()

        body = create(
            client, admin_headers, patient.id, files=attachment(name="Mein Befund.pdf")
        ).json()

        assert body["attachments"][0]["filename"] == "Mein Befund.pdf"

    def test_ohne_namen_bleibt_der_name_leer(self):
        """Kein erfundener Name: `null` heisst „der Aufrufer hat keinen geschickt".

        Ein hier zusammengebauter `<id>.bin` sähe im Frontend aus wie ein
        echter Dateiname des Benutzers.

        Geprüft wird gegen die Logik und nicht über HTTP: Ein Multipart-Teil
        ohne Dateinamen ist für Starlette ein gewöhnliches Formularfeld, der
        Fall kommt am Endpunkt also gar nicht erst an. Die Zusicherung gilt
        trotzdem — `service.create` ist der Ort, an dem der Name gesetzt wird.
        """
        document = documents_service.create(
            patient_id=1,
            metadata=DocumentMetadata(document_type="befund", title="Ohne Namen"),
            attachments=[
                documents_service.IncomingAttachment(
                    stream=io.BytesIO(b"inhalt"),
                    filename=None,
                    content_type="application/pdf",
                )
            ],
        )

        assert len(document.attachments) == 1
        assert document.attachments[0].filename is None

    @pytest.mark.parametrize(
        ("filename", "expected"),
        [
            ("befund.pdf", ".pdf"),
            ("scan.JPEG", ".JPEG"),
            ("ohne-endung", ""),
            ("../../etc/passwd", ""),
            ("boese.php%00.jpg", ".jpg"),
            ("x." + "a" * 40, ""),
            (None, ""),
        ],
    )
    def test_nur_harmlose_endungen_werden_uebernommen(self, filename, expected):
        assert safe_suffix(filename) == expected


class TestMehrereAnhaenge:
    """Ein Befund aus drei gescannten Seiten ist **ein** Dokument."""

    def test_ein_dokument_traegt_mehrere_anhaenge(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()

        body = create(
            client,
            admin_headers,
            patient.id,
            files=attachments(
                attachment(b"seite eins", "seite1.pdf"),
                attachment(b"seite zwei", "seite2.pdf"),
                attachment(b"seite drei", "seite3.pdf"),
            ),
        ).json()

        assert len(body["attachments"]) == 3
        assert [a["filename"] for a in body["attachments"]] == [
            "seite1.pdf",
            "seite2.pdf",
            "seite3.pdf",
        ]

    def test_jeder_anhang_bekommt_eine_eigene_kennung(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()

        body = create(
            client,
            admin_headers,
            patient.id,
            files=attachments(attachment(name="a.pdf"), attachment(name="b.pdf")),
        ).json()

        kennungen = [a["id"] for a in body["attachments"]]
        assert len(set(kennungen)) == 2

    def test_jeder_anhang_liegt_als_eigene_datei(
        self, client: TestClient, admin_headers, make_patient, upload_dir
    ):
        """Ein Ordner je Dokument — sonst überschrieben sie sich gegenseitig."""
        patient = make_patient()

        body = create(
            client,
            admin_headers,
            patient.id,
            files=attachments(
                attachment(b"erste bytes", "a.pdf"),
                attachment(b"zweite bytes", "b.pdf"),
            ),
        ).json()

        ordner = upload_dir / str(patient.id) / body["id"]
        dateien = sorted(p.read_bytes() for p in ordner.iterdir() if p.is_file())
        assert dateien == [b"erste bytes", b"zweite bytes"]

    def test_eine_herkunft_gilt_fuer_alle_anhaenge(
        self, client: TestClient, admin_headers, make_patient
    ):
        """Der übliche Fall: Ein dreiseitiger Scan kommt aus einer Praxis."""
        patient = make_patient()

        body = create(
            client,
            admin_headers,
            patient.id,
            source="Radiologie Mitte",
            files=attachments(attachment(name="a.pdf"), attachment(name="b.pdf")),
        ).json()

        assert [a["source"] for a in body["attachments"]] == [
            "Radiologie Mitte",
            "Radiologie Mitte",
        ]

    def test_je_anhang_eine_eigene_herkunft(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()

        response = client.post(
            docs_url(patient.id),
            files=attachments(attachment(name="a.pdf"), attachment(name="b.pdf")),
            data={
                "document_type": "befund",
                "title": "Zwei Quellen",
                "source": ["Radiologie Mitte", "Eigene Praxis"],
            },
            headers=admin_headers,
        )

        assert [a["source"] for a in response.json()["attachments"]] == [
            "Radiologie Mitte",
            "Eigene Praxis",
        ]

    def test_fehlende_herkunft_bleibt_leer(
        self, client: TestClient, admin_headers, make_patient
    ):
        """Weniger Angaben als Anhänge ist kein Fehler — `source` ist optional."""
        patient = make_patient()

        response = client.post(
            docs_url(patient.id),
            files=attachments(
                attachment(name="a.pdf"),
                attachment(name="b.pdf"),
                attachment(name="c.pdf"),
            ),
            data={
                "document_type": "befund",
                "title": "Nur eine Quelle benannt",
                "source": ["Radiologie Mitte", "Eigene Praxis"],
            },
            headers=admin_headers,
        )

        assert [a["source"] for a in response.json()["attachments"]] == [
            "Radiologie Mitte",
            "Eigene Praxis",
            None,
        ]

    def test_ein_zu_grosser_anhang_nimmt_die_frueheren_mit(
        self, client: TestClient, admin_headers, make_patient, upload_dir, monkeypatch
    ):
        """Es entsteht kein Dokument — also darf auch nichts liegenbleiben."""
        monkeypatch.setattr(settings, "max_upload_bytes", 1024)
        patient = make_patient()

        response = create(
            client,
            admin_headers,
            patient.id,
            files=attachments(
                attachment(b"x" * 100, "klein.pdf"),
                attachment(b"x" * 5000, "gross.pdf"),
            ),
        )

        assert response.status_code == 413
        assert client.get(docs_url(patient.id), headers=admin_headers).json()["total"] == 0
        assert [p for p in upload_dir.rglob("*") if p.is_file()] == []

    def test_zu_viele_anhaenge_werden_abgewiesen(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()

        response = create(
            client,
            admin_headers,
            patient.id,
            files=attachments(
                *[attachment(name=f"{i}.pdf") for i in range(MAX_ATTACHMENTS + 1)]
            ),
        )

        assert response.status_code == 422
        assert response.json()["errors"][0]["field"] == "files"

    def test_loeschen_nimmt_alle_anhaenge_mit(
        self, client: TestClient, admin_headers, make_patient, upload_dir
    ):
        patient = make_patient()
        document = create(
            client,
            admin_headers,
            patient.id,
            files=attachments(attachment(name="a.pdf"), attachment(name="b.pdf")),
        ).json()

        client.delete(f"{docs_url(patient.id)}/{document['id']}", headers=admin_headers)

        assert [p for p in upload_dir.rglob("*") if p.is_file()] == []


class TestAnhangAbrufen:
    """GET …/documents/{document_id}/attachments/{attachment_id}"""

    def test_liefert_die_bytes_zurueck(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()
        document = create(
            client, admin_headers, patient.id, files=attachment(b"%PDF-1.4 echt")
        ).json()

        response = client.get(document["attachments"][0]["url"], headers=admin_headers)

        assert response.status_code == 200
        assert response.content == b"%PDF-1.4 echt"

    def test_die_adresse_steht_fertig_in_der_antwort(
        self, client: TestClient, admin_headers, make_patient
    ):
        """Das Frontend soll sie nicht selbst zusammensetzen müssen."""
        patient = make_patient()
        document = create(client, admin_headers, patient.id).json()
        anhang = document["attachments"][0]

        assert anhang["url"] == (
            f"/patients/{patient.id}/documents/{document['id']}"
            f"/attachments/{anhang['id']}"
        )

    def test_typ_und_dateiname_kommen_mit(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()
        document = create(
            client,
            admin_headers,
            patient.id,
            files=attachment(name="Mein Befund.pdf", content_type="application/pdf"),
        ).json()

        response = client.get(document["attachments"][0]["url"], headers=admin_headers)

        assert response.headers["content-type"] == "application/pdf"
        # Starlette kodiert den Namen nach RFC 5987 — Leerzeichen wird %20.
        disposition = response.headers["content-disposition"]
        assert "Mein%20Befund.pdf" in disposition

    def test_wird_zum_ansehen_ausgeliefert_nicht_zum_speichern(
        self, client: TestClient, admin_headers, make_patient
    ):
        """Ein Scan soll sich im Browser öffnen lassen."""
        patient = make_patient()
        document = create(client, admin_headers, patient.id).json()

        response = client.get(document["attachments"][0]["url"], headers=admin_headers)

        assert response.headers["content-disposition"].startswith("inline")

    def test_die_download_adresse_erzwingt_den_speichern_dialog(
        self, client: TestClient, admin_headers, make_patient
    ):
        """Zwei Adressen, ein Endpunkt: `url` zeigt an, `download_url` lädt herunter."""
        patient = make_patient()
        document = create(client, admin_headers, patient.id).json()

        response = client.get(
            document["attachments"][0]["download_url"], headers=admin_headers
        )

        assert response.status_code == 200
        assert response.headers["content-disposition"].startswith("attachment")
        assert response.content == b"%PDF-1.4 Testinhalt"

    def test_beide_adressen_zeigen_auf_dieselbe_route(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()
        document = create(client, admin_headers, patient.id).json()
        anhang = document["attachments"][0]

        assert anhang["download_url"] == f"{anhang['url']}?download=true"

    def test_jeder_anhang_liefert_seine_eigenen_bytes(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()
        document = create(
            client,
            admin_headers,
            patient.id,
            files=attachments(
                attachment(b"seite eins", "a.pdf"),
                attachment(b"seite zwei", "b.pdf"),
            ),
        ).json()

        erster, zweiter = document["attachments"]

        assert client.get(erster["url"], headers=admin_headers).content == b"seite eins"
        assert client.get(zweiter["url"], headers=admin_headers).content == b"seite zwei"

    def test_staff_darf_anhaenge_lesen(
        self, client: TestClient, staff_headers, make_patient
    ):
        """ADR-0005: `staff` darf Dokumente lesen."""
        patient = make_patient()
        document = create(client, staff_headers, patient.id).json()

        response = client.get(document["attachments"][0]["url"], headers=staff_headers)

        assert response.status_code == 200

    def test_ohne_token_kein_anhang(self, client: TestClient, admin_headers, make_patient):
        patient = make_patient()
        document = create(client, admin_headers, patient.id).json()

        assert client.get(document["attachments"][0]["url"]).status_code == 401

    def test_unbekannte_anhang_kennung_liefert_404(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()
        document = create(client, admin_headers, patient.id).json()

        response = client.get(
            f"{docs_url(patient.id)}/{document['id']}/attachments/gibtesnicht",
            headers=admin_headers,
        )

        assert response.status_code == 404

    def test_unbekanntes_dokument_liefert_404(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()

        response = client.get(
            f"{docs_url(patient.id)}/gibtesnicht/attachments/auchnicht",
            headers=admin_headers,
        )

        assert response.status_code == 404

    def test_ein_fremder_anhang_ist_ueber_den_eigenen_patienten_nicht_zu_holen(
        self, client: TestClient, admin_headers, make_patient
    ):
        """Wer die Kennung errät, kommt trotzdem nicht heran."""
        fremder = make_patient(first_name="Max")
        eigener = make_patient(first_name="Erika")
        document = create(client, admin_headers, fremder.id).json()
        anhang = document["attachments"][0]

        response = client.get(
            f"{docs_url(eigener.id)}/{document['id']}/attachments/{anhang['id']}",
            headers=admin_headers,
        )

        assert response.status_code == 404

    def test_fehlt_die_datei_auf_der_platte_gibt_es_404_und_keinen_500(
        self, client: TestClient, admin_headers, make_patient, upload_dir
    ):
        """Die Angaben sagen, es gäbe ihn — auf der Platte liegt nichts."""
        patient = make_patient()
        document = create(client, admin_headers, patient.id).json()
        for datei in (upload_dir / str(patient.id) / document["id"]).iterdir():
            datei.unlink()

        response = client.get(document["attachments"][0]["url"], headers=admin_headers)

        assert response.status_code == 404

    def test_der_speicherort_wird_nicht_verraten(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()
        document = create(client, admin_headers, patient.id).json()

        assert "stored_as" not in str(document)


class TestAuflisten:
    """GET /patients/{patient_id}/documents"""

    def test_liefert_die_dokumente_des_patienten(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()
        create(client, admin_headers, patient.id, title="Erstes")
        create(client, admin_headers, patient.id, title="Zweites")

        response = client.get(docs_url(patient.id), headers=admin_headers)

        assert response.status_code == 200
        assert response.json()["total"] == 2
        assert len(response.json()["items"]) == 2

    def test_zeigt_nur_die_dokumente_dieses_patienten(
        self, client: TestClient, admin_headers, make_patient
    ):
        one = make_patient(first_name="Max")
        other = make_patient(first_name="Erika")
        create(client, admin_headers, one.id, title="Gehoert Max")
        create(client, admin_headers, other.id, title="Gehoert Erika")

        body = client.get(docs_url(one.id), headers=admin_headers).json()

        assert body["total"] == 1
        assert body["items"][0]["title"] == "Gehoert Max"

    def test_neueste_zuerst(self, client: TestClient, admin_headers, make_patient):
        patient = make_patient()
        for title in ("Erstes", "Zweites", "Drittes"):
            create(client, admin_headers, patient.id, title=title)

        items = client.get(docs_url(patient.id), headers=admin_headers).json()[
            "items"
        ]

        assert [d["title"] for d in items] == ["Drittes", "Zweites", "Erstes"]

    def test_suche_trifft_im_titel(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()
        create(client, admin_headers, patient.id, title="Befund MRT")
        create(client, admin_headers, patient.id, title="Laborwerte")

        body = client.get(
            docs_url(patient.id), params={"q": "mrt"}, headers=admin_headers
        ).json()

        assert body["total"] == 1
        assert body["items"][0]["title"] == "Befund MRT"

    def test_suche_trifft_in_der_beschreibung(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()
        create(
            client, admin_headers, patient.id, title="Befund", description="Knie links"
        )
        create(client, admin_headers, patient.id, title="Laborwerte")

        body = client.get(
            docs_url(patient.id), params={"q": "knie"}, headers=admin_headers
        ).json()

        assert body["total"] == 1

    @pytest.mark.parametrize("written_as", ["mrt", "MRT", "MrT"])
    def test_suche_ignoriert_die_schreibweise(
        self, client: TestClient, admin_headers, make_patient, written_as
    ):
        patient = make_patient()
        create(client, admin_headers, patient.id, title="Befund MRT")

        body = client.get(
            docs_url(patient.id),
            params={"q": written_as},
            headers=admin_headers,
        ).json()

        assert body["total"] == 1

    def test_kein_treffer_liefert_leere_liste(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()
        create(client, admin_headers, patient.id)

        response = client.get(
            docs_url(patient.id), params={"q": "gibtesnicht"}, headers=admin_headers
        )

        assert response.status_code == 200
        assert response.json()["items"] == []
        assert response.json()["total"] == 0

    def test_patient_ohne_dokumente_liefert_leere_liste(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()

        response = client.get(docs_url(patient.id), headers=admin_headers)

        assert response.status_code == 200
        assert response.json() == {"items": [], "total": 0, "limit": 100, "offset": 0}

    def test_limit_und_offset(self, client: TestClient, admin_headers, make_patient):
        patient = make_patient()
        for number in range(5):
            create(client, admin_headers, patient.id, title=f"Dokument {number}")

        body = client.get(
            docs_url(patient.id),
            params={"limit": 2, "offset": 2},
            headers=admin_headers,
        ).json()

        assert body["total"] == 5
        assert len(body["items"]) == 2
        assert body["limit"] == 2

    def test_zu_grosses_limit_wird_abgelehnt(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()

        response = client.get(
            docs_url(patient.id), params={"limit": 5000}, headers=admin_headers
        )

        assert response.status_code == 422

    def test_unbekannter_patient_liefert_404(self, client: TestClient, admin_headers):
        response = client.get(docs_url(999999), headers=admin_headers)

        assert response.status_code == 404

    def test_ohne_token_keine_liste(self, client: TestClient, make_patient):
        patient = make_patient()

        assert client.get(docs_url(patient.id)).status_code == 401


class TestSuchePredikat:
    """Beide Speicher müssen dieselben Felder durchsuchen.

    Die Tests laufen gegen den Speicher-Store — driftete der Mongo-Filter weg,
    bliebe die Suite grün und die echte Suche wäre falsch. Deshalb hier
    ausdrücklich: beide leiten sich aus `SEARCHED_FIELDS` ab.
    """

    def test_der_mongo_filter_durchsucht_genau_diese_felder(self):
        query = _search_filter(1, "mrt")

        assert {next(iter(part)) for part in query["$or"]} == set(SEARCHED_FIELDS)

    def test_das_speicher_predikat_durchsucht_genau_diese_felder(self):
        for field in SEARCHED_FIELDS:
            assert matches_term({field: "Treffer hier"}, "treffer")

    def test_ein_leerer_begriff_trifft_alles(self):
        assert matches_term({"title": "irgendwas"}, normalize_term("   "))

    def test_ein_fehlendes_feld_ist_kein_absturz(self):
        assert not matches_term({}, "mrt")


class TestLoeschen:
    """DELETE /patients/{patient_id}/documents/{document_id}"""

    def test_loescht_das_dokument_und_liefert_204(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()
        document = create(client, admin_headers, patient.id).json()

        response = client.delete(
            f"{docs_url(patient.id)}/{document['id']}", headers=admin_headers
        )

        assert response.status_code == 204
        assert (
            client.get(docs_url(patient.id), headers=admin_headers).json()["total"]
            == 0
        )

    def test_loescht_auch_den_anhang(
        self, client: TestClient, admin_headers, make_patient, upload_dir
    ):
        """Sonst wächst die Platte, während die Liste leer aussieht."""
        patient = make_patient()
        document = create(client, admin_headers, patient.id).json()

        client.delete(f"{docs_url(patient.id)}/{document['id']}", headers=admin_headers)

        assert [p for p in upload_dir.rglob("*") if p.is_file()] == []

    def test_loescht_nur_das_gemeinte_dokument(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()
        doomed = create(client, admin_headers, patient.id, title="Weg").json()
        create(client, admin_headers, patient.id, title="Bleibt")

        client.delete(f"{docs_url(patient.id)}/{doomed['id']}", headers=admin_headers)

        items = client.get(docs_url(patient.id), headers=admin_headers).json()[
            "items"
        ]
        assert [d["title"] for d in items] == ["Bleibt"]

    def test_unbekanntes_dokument_liefert_404(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()

        response = client.delete(
            f"{docs_url(patient.id)}/gibtesnicht", headers=admin_headers
        )

        assert response.status_code == 404
        assert "gibtesnicht" in response.json()["message"]

    def test_zweimaliges_loeschen_ist_kein_serverfehler(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()
        document = create(client, admin_headers, patient.id).json()

        first = client.delete(
            f"{docs_url(patient.id)}/{document['id']}", headers=admin_headers
        )
        second = client.delete(
            f"{docs_url(patient.id)}/{document['id']}", headers=admin_headers
        )

        assert first.status_code == 204
        assert second.status_code == 404

    def test_fremdes_dokument_laesst_sich_nicht_ueber_einen_anderen_patienten_loeschen(
        self, client: TestClient, admin_headers, make_patient
    ):
        """Die Patienten-ID im Pfad ist nicht nur Zierde."""
        one = make_patient(first_name="Max")
        other = make_patient(first_name="Erika")
        document = create(client, admin_headers, one.id).json()

        response = client.delete(
            f"{docs_url(other.id)}/{document['id']}", headers=admin_headers
        )

        assert response.status_code == 404
        assert (
            client.get(docs_url(one.id), headers=admin_headers).json()["total"] == 1
        )

    def test_staff_darf_nicht_loeschen(
        self, client: TestClient, staff_headers, admin_headers, make_patient
    ):
        """ADR-0005 gibt `staff` Lesen und Anlegen — Löschen nicht."""
        patient = make_patient()
        document = create(client, admin_headers, patient.id).json()

        response = client.delete(
            f"{docs_url(patient.id)}/{document['id']}", headers=staff_headers
        )

        assert response.status_code == 403
        assert (
            client.get(docs_url(patient.id), headers=staff_headers).json()["total"]
            == 1
        )


class TestPatientGeloescht:
    """Die Akte geht mit dem Patienten."""

    def test_dokumente_verschwinden_mit_dem_patienten(
        self, client: TestClient, admin_headers, make_patient, documents
    ):
        """Sonst blieben sie unerreichbar in der Datenbank stehen."""
        patient = make_patient()
        create(client, admin_headers, patient.id, title="Eins")
        create(client, admin_headers, patient.id, title="Zwei")

        client.delete(f"/patients/{patient.id}", headers=admin_headers)

        assert documents.search(patient.id, None, 100, 0) == ([], 0)

    def test_die_anhaenge_verschwinden_mit(
        self, client: TestClient, admin_headers, make_patient, upload_dir
    ):
        patient = make_patient()
        create(client, admin_headers, patient.id)

        client.delete(f"/patients/{patient.id}", headers=admin_headers)

        assert not (upload_dir / str(patient.id)).exists()

    def test_andere_patienten_bleiben_unberuehrt(
        self, client: TestClient, admin_headers, make_patient, upload_dir
    ):
        one = make_patient(first_name="Max")
        other = make_patient(first_name="Erika")
        create(client, admin_headers, one.id)
        create(client, admin_headers, other.id)

        client.delete(f"/patients/{one.id}", headers=admin_headers)

        assert (
            client.get(docs_url(other.id), headers=admin_headers).json()["total"] == 1
        )
        assert (upload_dir / str(other.id)).exists()

    def test_die_anzahl_steht_im_audit_trail(
        self, client: TestClient, admin_headers, make_patient, audit_store
    ):
        patient = make_patient()
        create(client, admin_headers, patient.id, title="Eins")
        create(client, admin_headers, patient.id, title="Zwei")

        client.delete(f"/patients/{patient.id}", headers=admin_headers)

        found = [
            e for e in audit_store.recent(500) if e["event"] == EventType.PATIENT_DELETED
        ]
        assert found[0]["detail"]["documents_removed"] == 2

    def test_patient_ohne_dokumente_laesst_sich_normal_loeschen(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()

        assert (
            client.delete(f"/patients/{patient.id}", headers=admin_headers).status_code
            == 204
        )

    def test_der_trail_ueberlebt_eine_gescheiterte_kaskade(
        self,
        client: TestClient,
        admin_headers,
        make_patient,
        documents,
        audit_store,
        monkeypatch,
    ):
        """Der wichtigste Fall am Löschen eines Patienten.

        Der Patient ist in Postgres schon weg; ab hier ist der Trail-Eintrag
        der einzige Beleg, dass es ihn je gab. Räumt MongoDB nicht ab, darf
        genau dieser Eintrag nicht mit verlorengehen.
        """
        patient = make_patient()
        create(client, admin_headers, patient.id)

        def fails(_patient_id):
            raise RuntimeError("MongoDB antwortet nicht")

        monkeypatch.setattr(documents, "delete_for_patient", fails)

        response = client.delete(f"/patients/{patient.id}", headers=admin_headers)

        # Der Fehler wird nicht verschluckt — der Aufrufer sieht, dass etwas
        # schiefging. Der Beleg im Trail steht trotzdem.
        assert response.status_code == 500
        found = [
            e for e in audit_store.recent(500) if e["event"] == EventType.PATIENT_DELETED
        ]
        assert len(found) == 1
        # `null`, nicht `0` — wie viele es waren, weiss niemand.
        assert found[0]["detail"]["documents_removed"] is None

    def test_die_anhaenge_gehen_auch_dann_weg_wenn_die_angaben_bleiben(
        self,
        client: TestClient,
        admin_headers,
        make_patient,
        documents,
        upload_dir,
        monkeypatch,
    ):
        """Sonst lägen die Bytes für immer da, ohne dass sie jemand findet.

        Der Patient ist zu diesem Zeitpunkt in Postgres schon weg, und ohne ihn
        führt kein Endpunkt mehr zu seinen Anhängen.
        """
        patient = make_patient()
        create(client, admin_headers, patient.id)
        assert (upload_dir / str(patient.id)).exists()

        def fails(_patient_id):
            raise RuntimeError("MongoDB antwortet nicht")

        monkeypatch.setattr(documents, "delete_for_patient", fails)

        response = client.delete(f"/patients/{patient.id}", headers=admin_headers)

        assert response.status_code == 500
        assert not (upload_dir / str(patient.id)).exists()

    def test_eine_gescheiterte_ablage_wird_nicht_als_erfolg_gemeldet(
        self, client: TestClient, admin_headers, make_patient, monkeypatch
    ):
        """`204` mit einer Zahl daneben behauptete sonst ein Aufräumen, das nicht war.

        Anders als beim Löschen eines einzelnen Dokuments wird der Fehler hier
        **nicht** geschluckt: Dort ist das Dokument ohnehin schon weg, hier
        bliebe alles liegen, was von einem Patienten übrig ist.
        """
        patient = make_patient()
        create(client, admin_headers, patient.id)

        # Die Attrappe verhält sich wie das echte `shutil.rmtree`: Mit
        # `ignore_errors=True` schweigt sie. Genau daran hing der Fehler — die
        # Ablage rief so auf, und ein nicht abgeräumter Ordner wurde zu einer
        # `204`. Wer das Flag wieder einbaut, bekommt diesen Test rot.
        def rmtree_fails(_path, *, ignore_errors=False, **_kwargs):
            if ignore_errors:
                return
            raise OSError("Ordner laesst sich nicht entfernen")

        monkeypatch.setattr(documents_storage.shutil, "rmtree", rmtree_fails)

        response = client.delete(f"/patients/{patient.id}", headers=admin_headers)

        assert response.status_code == 500

    def test_ein_ordner_den_es_nie_gab_ist_kein_fehler(
        self, client: TestClient, admin_headers, make_patient, upload_dir
    ):
        """Ein Patient ohne Dokumente hat nie einen Ordner bekommen."""
        patient = make_patient()
        assert not (upload_dir / str(patient.id)).exists()

        response = client.delete(f"/patients/{patient.id}", headers=admin_headers)

        assert response.status_code == 204


class TestOhneMongo:
    """Für Dokumente gibt es keinen stillen Rückfall in den Speicher."""

    def test_ohne_mongo_url_gibt_es_keinen_speicher_ersatz(self, monkeypatch):
        """Ein Dokument, das den Neustart nicht überlebt, ist ein verlorener Befund.

        Der Audit-Trail darf das (ADR-0007), die Akte nicht: Das Anlegen
        meldete `201`, der Anhang läge wirklich auf der Platte, und nach dem
        nächsten Start wäre das Dokument weg — ohne dass etwas schiefging.
        """
        monkeypatch.setattr(settings, "mongo_url", "")

        with pytest.raises(RuntimeError, match="MONGO_URL"):
            documents_store._build_store()


class TestZeitzone:
    """`created_at` kommt aus MongoDB **mit** Zeitzone zurück."""

    def test_der_dokumentenspeicher_liest_zeitpunkte_mit_zeitzone(
        self, fake_pymongo
    ):
        """Ohne `tz_aware` fehlte in der Antwort das `Z` — und zwar nur im Betrieb.

        BSON speichert einen Zeitpunkt in UTC, aber ohne die Zonenangabe. Beim
        Lesen käme er deshalb ohne `tzinfo` zurück, und aus
        "2026-07-21T08:10:00Z" würde in der Antwort "2026-07-21T08:10:00" — ein
        Zeitstempel, den ein Browser als **lokale** Zeit liest. Kein Test gegen
        den Speicher-Store könnte das sehen: Der gibt das Python-Objekt
        unverändert zurück, samt Zeitzone. Deshalb steht hier die Einstellung
        selbst.
        """
        documents_store.MongoDocumentStore("mongodb://mongo:27017", "medidoc")

        assert fake_pymongo[0].options["tz_aware"] is True


class TestAuditTrail:
    """Anlegen und Löschen sind nachvollziehbar — ohne Patientendaten."""

    def test_anlegen_wird_festgehalten(
        self, client: TestClient, admin_headers, make_patient, audit_store
    ):
        patient = make_patient()

        document = create(client, admin_headers, patient.id).json()

        found = [
            e for e in audit_store.recent(500) if e["event"] == EventType.DOCUMENT_CREATED
        ]
        assert len(found) == 1
        assert found[0]["target"] == f"document:{document['id']}"
        assert found[0]["detail"]["patient"] == f"patient:{patient.id}"
        assert found[0]["detail"]["document_type"] == "befund"

    def test_loeschen_wird_festgehalten(
        self, client: TestClient, admin_headers, make_patient, audit_store
    ):
        patient = make_patient()
        document = create(client, admin_headers, patient.id).json()

        client.delete(f"{docs_url(patient.id)}/{document['id']}", headers=admin_headers)

        found = [
            e for e in audit_store.recent(500) if e["event"] == EventType.DOCUMENT_DELETED
        ]
        assert len(found) == 1

    def test_weder_dateiname_noch_titel_landen_im_trail(
        self, client: TestClient, admin_headers, make_patient, audit_store
    ):
        """Beide tragen in der Praxis Patientennamen."""
        patient = make_patient()

        create(
            client,
            admin_headers,
            patient.id,
            title="Mueller Befund",
            files=attachment(name="Mueller_Roentgen.pdf"),
        )

        trail = str(audit_store.recent(500))
        assert "Mueller" not in trail
        assert "Roentgen" not in trail

    def test_die_herkunft_bleibt_draussen(
        self, client: TestClient, admin_headers, make_patient, audit_store
    ):
        """`source` ist Freitext — dort landet in der Praxis alles."""
        patient = make_patient()

        create(client, admin_headers, patient.id, source="Praxis Erika Mustermann")

        assert "Mustermann" not in str(audit_store.recent(500))


class TestTags:
    """`tags` kommt kommagetrennt herein und geht als Liste hinaus."""

    @pytest.mark.parametrize(
        ("given", "expected"),
        [
            ("mrt, radiologie", ["mrt", "radiologie"]),
            ("MRT,Radiologie", ["mrt", "radiologie"]),
            ("  mrt  ,,  ", ["mrt"]),
            ("mrt, MRT, mrt", ["mrt"]),
            ("", []),
            (None, []),
        ],
    )
    def test_parse_tags(self, given, expected):
        assert parse_tags(given) == expected

    def test_tags_kommen_als_liste_zurueck(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()

        body = create(
            client, admin_headers, patient.id, tags="mrt, Radiologie, mrt"
        ).json()

        assert body["tags"] == ["mrt", "radiologie"]

    def test_die_reihenfolge_bleibt_stabil(
        self, client: TestClient, admin_headers, make_patient
    ):
        """Sonst flackerte die Liste im Frontend bei jedem Laden."""
        patient = make_patient()

        first = create(client, admin_headers, patient.id, tags="c, a, b").json()
        second = create(client, admin_headers, patient.id, tags="c, a, b").json()

        assert first["tags"] == second["tags"] == ["c", "a", "b"]


class TestNichtsWirdVerraten:
    """Interna gehören nicht in die Antwort."""

    def test_speicherort_und_urheber_gehen_nicht_hinaus(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()

        response = create(client, admin_headers, patient.id)

        assert "stored_as" not in response.text
        assert "sha256" not in response.text
        assert "created_by" not in response.text


def test_die_swagger_oberflaeche_bleibt_erreichbar(client: TestClient):
    """Der Pfad `/docs` gehört auch FastAPIs eigener Oberfläche.

    Sie liegt auf dem exakten Pfad, unsere Routen beginnen erst darunter — das
    hier ist der Wächter dafür, dass es so bleibt.
    """
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_die_gepruefte_route_existiert_wirklich(
    client: TestClient, admin_headers, make_patient
):
    """Wächter: Ein Tippfehler im Pfad würde sonst überall 404 liefern."""
    patient = make_patient()

    assert client.get(docs_url(patient.id), headers=admin_headers).status_code == 200
