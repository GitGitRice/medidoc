"""Dokumente zu einem Patienten — ein Test pro Akzeptanzkriterium.

Der Vertrag steht in docs/documents-api.md. Gegliedert nach Endpunkt, dazu die
beiden Blöcke, die bei einem Datei-Upload am meisten wehtun, wenn sie fehlen:
die Größenprüfung und die Ablage auf der Platte.

Läuft gegen den Speicher-Store und einen `tmp_path`-Ordner — kein MongoDB, kein
Docker (siehe `documents`-Fixture in conftest.py).
"""

import io

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.modules.audit.events import EventType
from app.modules.documents.schemas import parse_tags
from app.modules.documents.storage import safe_suffix

BASE = "/docs"


def datei(inhalt: bytes = b"%PDF-1.4 Testinhalt", name: str = "befund.pdf", typ: str = "application/pdf"):
    return {"file": (name, io.BytesIO(inhalt), typ)}


def hochladen(client: TestClient, headers, patient_id: int, **felder):
    """Ein Upload, wie ihn das Formular im Frontend schickt.

    `files` muss vor dem Zusammenbauen heraus — sonst landete die Datei als
    Formularfeld in `data`.
    """
    dateien = felder.pop("files", None) or datei()
    daten = {"title": "Befund MRT"} | felder
    return client.post(
        f"{BASE}/{patient_id}",
        files=dateien,
        data=daten,
        headers=headers,
    )


class TestHochladen:
    """POST /docs/{patient_id}"""

    def test_legt_das_dokument_an_und_liefert_201(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()

        antwort = hochladen(client, admin_headers, patient.id)

        assert antwort.status_code == 201
        body = antwort.json()
        assert body["title"] == "Befund MRT"
        assert body["patient_id"] == patient.id
        assert body["id"]

    def test_uebernimmt_alle_angaben(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()

        body = hochladen(
            client,
            admin_headers,
            patient.id,
            title="Laborwerte Januar",
            description="Grosses Blutbild",
            tags="labor, blutbild",
            source="Labor Berlin",
        ).json()

        assert body["title"] == "Laborwerte Januar"
        assert body["description"] == "Grosses Blutbild"
        assert body["tags"] == ["labor", "blutbild"]
        assert body["source"] == "Labor Berlin"
        assert body["created_at"]

    def test_liefert_die_dateiangaben_mit(
        self, client: TestClient, admin_headers, make_patient
    ):
        """Ohne Dateiname und Größe wäre die Liste im Frontend nicht bedienbar."""
        patient = make_patient()

        body = hochladen(client, admin_headers, patient.id).json()

        assert body["filename"] == "befund.pdf"
        assert body["content_type"] == "application/pdf"
        assert body["size_bytes"] == len(b"%PDF-1.4 Testinhalt")

    def test_nur_titel_und_datei_reichen(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()

        body = hochladen(client, admin_headers, patient.id).json()

        assert body["description"] is None
        assert body["source"] is None
        assert body["tags"] == []

    def test_fehlender_titel_liefert_422(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()

        antwort = client.post(
            f"{BASE}/{patient.id}", files=datei(), headers=admin_headers
        )

        assert antwort.status_code == 422
        assert antwort.json()["message"] == "Pflichtfeld fehlt: title"

    def test_leerer_titel_liefert_422(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()

        antwort = hochladen(client, admin_headers, patient.id, title="   ")

        assert antwort.status_code == 422

    def test_fehlende_datei_liefert_422(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()

        antwort = client.post(
            f"{BASE}/{patient.id}", data={"title": "Ohne Datei"}, headers=admin_headers
        )

        assert antwort.status_code == 422
        assert antwort.json()["errors"][0]["field"] == "file"

    def test_unbekannter_patient_liefert_404(self, client: TestClient, admin_headers):
        antwort = hochladen(client, admin_headers, 999999)

        assert antwort.status_code == 404
        assert antwort.json()["message"] == "Patient mit der ID 999999 wurde nicht gefunden"

    def test_staff_darf_hochladen(
        self, client: TestClient, staff_headers, make_patient
    ):
        """ADR-0005: `staff` darf Dokumente lesen und anlegen."""
        patient = make_patient()

        assert hochladen(client, staff_headers, patient.id).status_code == 201

    def test_ohne_token_kein_upload(self, client: TestClient, make_patient):
        patient = make_patient()

        antwort = client.post(f"{BASE}/{patient.id}", files=datei(), data={"title": "X"})

        assert antwort.status_code == 401


class TestDateigroesse:
    """Die ausdrückliche Anforderung: höchstens 20 MB."""

    def test_die_grenze_liegt_bei_20_mb(self):
        assert settings.max_upload_bytes == 20 * 1024 * 1024

    def test_datei_knapp_unter_der_grenze_wird_angenommen(
        self, client: TestClient, admin_headers, make_patient, monkeypatch
    ):
        # Die Grenze wird heruntergedreht, statt 20 MB durch den Test zu
        # schieben — geprüft wird die Regel, nicht die Geduld.
        monkeypatch.setattr(settings, "max_upload_bytes", 1024)
        patient = make_patient()

        antwort = hochladen(
            client, admin_headers, patient.id, files=datei(b"x" * 1024)
        )

        assert antwort.status_code == 201
        assert antwort.json()["size_bytes"] == 1024

    def test_datei_ueber_der_grenze_liefert_413(
        self, client: TestClient, admin_headers, make_patient, monkeypatch
    ):
        monkeypatch.setattr(settings, "max_upload_bytes", 1024)
        patient = make_patient()

        antwort = hochladen(
            client, admin_headers, patient.id, files=datei(b"x" * 1025)
        )

        assert antwort.status_code == 413
        assert antwort.json()["status"] == 413
        assert "MB" in antwort.json()["message"]

    def test_eine_zu_grosse_datei_wird_nicht_angelegt(
        self, client: TestClient, admin_headers, make_patient, documents, monkeypatch
    ):
        """Kein halbes Dokument in der Liste."""
        monkeypatch.setattr(settings, "max_upload_bytes", 1024)
        patient = make_patient()

        hochladen(client, admin_headers, patient.id, files=datei(b"x" * 5000))

        assert client.get(f"{BASE}/{patient.id}", headers=admin_headers).json()["total"] == 0

    def test_eine_zu_grosse_datei_laesst_nichts_auf_der_platte(
        self, client: TestClient, admin_headers, make_patient, upload_dir, monkeypatch
    ):
        """Auch keine angefangene `.part`-Datei."""
        monkeypatch.setattr(settings, "max_upload_bytes", 1024)
        patient = make_patient()

        hochladen(client, admin_headers, patient.id, files=datei(b"x" * 5000))

        assert list(upload_dir.rglob("*")) == [] or all(
            p.is_dir() for p in upload_dir.rglob("*")
        )

    def test_leere_datei_liefert_422(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()

        antwort = hochladen(client, admin_headers, patient.id, files=datei(b""))

        assert antwort.status_code == 422
        assert antwort.json()["message"] == "Die Datei ist leer"


class TestAblage:
    """Was auf der Platte passiert."""

    def test_die_datei_liegt_wirklich_da(
        self, client: TestClient, admin_headers, make_patient, upload_dir
    ):
        patient = make_patient()
        inhalt = b"%PDF-1.4 echter Inhalt"

        antwort = hochladen(client, admin_headers, patient.id, files=datei(inhalt))

        gefunden = list((upload_dir / str(patient.id)).glob("*"))
        assert len(gefunden) == 1
        assert gefunden[0].read_bytes() == inhalt
        assert antwort.json()["id"] in gefunden[0].name

    def test_jeder_patient_bekommt_einen_eigenen_ordner(
        self, client: TestClient, admin_headers, make_patient, upload_dir
    ):
        einer = make_patient(first_name="Max")
        anderer = make_patient(first_name="Erika")

        hochladen(client, admin_headers, einer.id)
        hochladen(client, admin_headers, anderer.id)

        assert {p.name for p in upload_dir.iterdir()} == {
            str(einer.id),
            str(anderer.id),
        }

    def test_der_dateiname_des_aufrufers_wird_nie_zum_pfad(
        self, client: TestClient, admin_headers, make_patient, upload_dir
    ):
        """Der wichtigste Test dieser Datei.

        `../../` im Dateinamen darf nicht dazu führen, dass irgendetwas
        außerhalb des Upload-Ordners landet.
        """
        patient = make_patient()

        antwort = hochladen(
            client,
            admin_headers,
            patient.id,
            files=datei(b"boese", name="../../../etc/passwd"),
        )

        assert antwort.status_code == 201
        geschrieben = [p for p in upload_dir.rglob("*") if p.is_file()]
        assert len(geschrieben) == 1
        # Die Datei liegt im Ordner des Patienten, ihr Name ist die Kennung.
        assert geschrieben[0].parent == upload_dir / str(patient.id)
        assert antwort.json()["id"] in geschrieben[0].name

    def test_der_urspruengliche_name_bleibt_als_angabe_erhalten(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()

        body = hochladen(
            client, admin_headers, patient.id, files=datei(name="Mein Befund.pdf")
        ).json()

        assert body["filename"] == "Mein Befund.pdf"

    @pytest.mark.parametrize(
        ("dateiname", "erwartet"),
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
    def test_nur_harmlose_endungen_werden_uebernommen(self, dateiname, erwartet):
        assert safe_suffix(dateiname) == erwartet


class TestAuflisten:
    """GET /docs/{patient_id}"""

    def test_liefert_die_dokumente_des_patienten(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()
        hochladen(client, admin_headers, patient.id, title="Erstes")
        hochladen(client, admin_headers, patient.id, title="Zweites")

        antwort = client.get(f"{BASE}/{patient.id}", headers=admin_headers)

        assert antwort.status_code == 200
        assert antwort.json()["total"] == 2
        assert len(antwort.json()["items"]) == 2

    def test_zeigt_nur_die_dokumente_dieses_patienten(
        self, client: TestClient, admin_headers, make_patient
    ):
        einer = make_patient(first_name="Max")
        anderer = make_patient(first_name="Erika")
        hochladen(client, admin_headers, einer.id, title="Gehoert Max")
        hochladen(client, admin_headers, anderer.id, title="Gehoert Erika")

        body = client.get(f"{BASE}/{einer.id}", headers=admin_headers).json()

        assert body["total"] == 1
        assert body["items"][0]["title"] == "Gehoert Max"

    def test_neueste_zuerst(self, client: TestClient, admin_headers, make_patient):
        patient = make_patient()
        for titel in ("Erstes", "Zweites", "Drittes"):
            hochladen(client, admin_headers, patient.id, title=titel)

        items = client.get(f"{BASE}/{patient.id}", headers=admin_headers).json()["items"]

        assert [d["title"] for d in items] == ["Drittes", "Zweites", "Erstes"]

    def test_suche_trifft_im_titel(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()
        hochladen(client, admin_headers, patient.id, title="Befund MRT")
        hochladen(client, admin_headers, patient.id, title="Laborwerte")

        body = client.get(
            f"{BASE}/{patient.id}", params={"q": "mrt"}, headers=admin_headers
        ).json()

        assert body["total"] == 1
        assert body["items"][0]["title"] == "Befund MRT"

    def test_suche_trifft_in_der_beschreibung(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()
        hochladen(
            client, admin_headers, patient.id, title="Befund", description="Knie links"
        )
        hochladen(client, admin_headers, patient.id, title="Laborwerte")

        body = client.get(
            f"{BASE}/{patient.id}", params={"q": "knie"}, headers=admin_headers
        ).json()

        assert body["total"] == 1

    @pytest.mark.parametrize("geschrieben_als", ["mrt", "MRT", "MrT"])
    def test_suche_ignoriert_die_schreibweise(
        self, client: TestClient, admin_headers, make_patient, geschrieben_als
    ):
        patient = make_patient()
        hochladen(client, admin_headers, patient.id, title="Befund MRT")

        body = client.get(
            f"{BASE}/{patient.id}",
            params={"q": geschrieben_als},
            headers=admin_headers,
        ).json()

        assert body["total"] == 1

    def test_kein_treffer_liefert_leere_liste(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()
        hochladen(client, admin_headers, patient.id)

        antwort = client.get(
            f"{BASE}/{patient.id}", params={"q": "gibtesnicht"}, headers=admin_headers
        )

        assert antwort.status_code == 200
        assert antwort.json()["items"] == []
        assert antwort.json()["total"] == 0

    def test_patient_ohne_dokumente_liefert_leere_liste(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()

        antwort = client.get(f"{BASE}/{patient.id}", headers=admin_headers)

        assert antwort.status_code == 200
        assert antwort.json() == {"items": [], "total": 0, "limit": 100, "offset": 0}

    def test_limit_und_offset(self, client: TestClient, admin_headers, make_patient):
        patient = make_patient()
        for nummer in range(5):
            hochladen(client, admin_headers, patient.id, title=f"Dokument {nummer}")

        body = client.get(
            f"{BASE}/{patient.id}",
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

        antwort = client.get(
            f"{BASE}/{patient.id}", params={"limit": 5000}, headers=admin_headers
        )

        assert antwort.status_code == 422

    def test_unbekannter_patient_liefert_404(self, client: TestClient, admin_headers):
        antwort = client.get(f"{BASE}/999999", headers=admin_headers)

        assert antwort.status_code == 404

    def test_ohne_token_keine_liste(self, client: TestClient, make_patient):
        patient = make_patient()

        assert client.get(f"{BASE}/{patient.id}").status_code == 401


class TestLoeschen:
    """DELETE /docs/{patient_id}/{document_id}"""

    def test_loescht_das_dokument_und_liefert_204(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()
        dokument = hochladen(client, admin_headers, patient.id).json()

        antwort = client.delete(
            f"{BASE}/{patient.id}/{dokument['id']}", headers=admin_headers
        )

        assert antwort.status_code == 204
        assert client.get(f"{BASE}/{patient.id}", headers=admin_headers).json()["total"] == 0

    def test_loescht_auch_die_datei(
        self, client: TestClient, admin_headers, make_patient, upload_dir
    ):
        """Sonst wächst die Platte, während die Liste leer aussieht."""
        patient = make_patient()
        dokument = hochladen(client, admin_headers, patient.id).json()

        client.delete(f"{BASE}/{patient.id}/{dokument['id']}", headers=admin_headers)

        assert [p for p in upload_dir.rglob("*") if p.is_file()] == []

    def test_loescht_nur_das_gemeinte_dokument(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()
        opfer = hochladen(client, admin_headers, patient.id, title="Weg").json()
        hochladen(client, admin_headers, patient.id, title="Bleibt")

        client.delete(f"{BASE}/{patient.id}/{opfer['id']}", headers=admin_headers)

        items = client.get(f"{BASE}/{patient.id}", headers=admin_headers).json()["items"]
        assert [d["title"] for d in items] == ["Bleibt"]

    def test_unbekanntes_dokument_liefert_404(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()

        antwort = client.delete(
            f"{BASE}/{patient.id}/gibtesnicht", headers=admin_headers
        )

        assert antwort.status_code == 404
        assert "gibtesnicht" in antwort.json()["message"]

    def test_zweimaliges_loeschen_ist_kein_serverfehler(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()
        dokument = hochladen(client, admin_headers, patient.id).json()

        erster = client.delete(
            f"{BASE}/{patient.id}/{dokument['id']}", headers=admin_headers
        )
        zweiter = client.delete(
            f"{BASE}/{patient.id}/{dokument['id']}", headers=admin_headers
        )

        assert erster.status_code == 204
        assert zweiter.status_code == 404

    def test_fremdes_dokument_laesst_sich_nicht_ueber_einen_anderen_patienten_loeschen(
        self, client: TestClient, admin_headers, make_patient
    ):
        """Die Patienten-ID im Pfad ist nicht nur Zierde."""
        einer = make_patient(first_name="Max")
        anderer = make_patient(first_name="Erika")
        dokument = hochladen(client, admin_headers, einer.id).json()

        antwort = client.delete(
            f"{BASE}/{anderer.id}/{dokument['id']}", headers=admin_headers
        )

        assert antwort.status_code == 404
        assert client.get(f"{BASE}/{einer.id}", headers=admin_headers).json()["total"] == 1

    def test_staff_darf_nicht_loeschen(
        self, client: TestClient, staff_headers, admin_headers, make_patient
    ):
        """ADR-0005 gibt `staff` Lesen und Anlegen — Löschen nicht."""
        patient = make_patient()
        dokument = hochladen(client, admin_headers, patient.id).json()

        antwort = client.delete(
            f"{BASE}/{patient.id}/{dokument['id']}", headers=staff_headers
        )

        assert antwort.status_code == 403
        assert client.get(f"{BASE}/{patient.id}", headers=staff_headers).json()["total"] == 1


class TestAuditTrail:
    """Uploads und Löschungen sind nachvollziehbar — ohne Patientendaten."""

    def test_upload_wird_festgehalten(
        self, client: TestClient, admin_headers, make_patient, audit_store
    ):
        patient = make_patient()

        dokument = hochladen(client, admin_headers, patient.id).json()

        treffer = [
            e for e in audit_store.recent(500) if e["event"] == EventType.DOCUMENT_UPLOADED
        ]
        assert len(treffer) == 1
        assert treffer[0]["target"] == f"document:{dokument['id']}"
        assert treffer[0]["detail"]["patient"] == f"patient:{patient.id}"

    def test_loeschen_wird_festgehalten(
        self, client: TestClient, admin_headers, make_patient, audit_store
    ):
        patient = make_patient()
        dokument = hochladen(client, admin_headers, patient.id).json()

        client.delete(f"{BASE}/{patient.id}/{dokument['id']}", headers=admin_headers)

        treffer = [
            e for e in audit_store.recent(500) if e["event"] == EventType.DOCUMENT_DELETED
        ]
        assert len(treffer) == 1

    def test_weder_dateiname_noch_titel_landen_im_trail(
        self, client: TestClient, admin_headers, make_patient, audit_store
    ):
        """Beide tragen in der Praxis Patientennamen."""
        patient = make_patient()

        hochladen(
            client,
            admin_headers,
            patient.id,
            title="Mueller Befund",
            files=datei(name="Mueller_Roentgen.pdf"),
        )

        trail = str(audit_store.recent(500))
        assert "Mueller" not in trail
        assert "Roentgen" not in trail


class TestTags:
    """`tags` kommt kommagetrennt herein und geht als Liste hinaus."""

    @pytest.mark.parametrize(
        ("eingabe", "erwartet"),
        [
            ("mrt, radiologie", ["mrt", "radiologie"]),
            ("MRT,Radiologie", ["mrt", "radiologie"]),
            ("  mrt  ,,  ", ["mrt"]),
            ("mrt, MRT, mrt", ["mrt"]),
            ("", []),
            (None, []),
        ],
    )
    def test_parse_tags(self, eingabe, erwartet):
        assert parse_tags(eingabe) == erwartet

    def test_tags_kommen_als_liste_zurueck(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()

        body = hochladen(
            client, admin_headers, patient.id, tags="mrt, Radiologie, mrt"
        ).json()

        assert body["tags"] == ["mrt", "radiologie"]

    def test_die_reihenfolge_bleibt_stabil(
        self, client: TestClient, admin_headers, make_patient
    ):
        """Sonst flackerte die Liste im Frontend bei jedem Laden."""
        patient = make_patient()

        erste = hochladen(client, admin_headers, patient.id, tags="c, a, b").json()
        zweite = hochladen(client, admin_headers, patient.id, tags="c, a, b").json()

        assert erste["tags"] == zweite["tags"] == ["c", "a", "b"]


class TestNichtsWirdVerraten:
    """Interna gehören nicht in die Antwort."""

    def test_speicherort_und_pruefsumme_gehen_nicht_hinaus(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()

        antwort = hochladen(client, admin_headers, patient.id)

        assert "stored_as" not in antwort.text
        assert "sha256" not in antwort.text
        assert "uploaded_by" not in antwort.text


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
    """Wächter: Ein Tippfehler in BASE würde sonst überall 404 liefern."""
    patient = make_patient()

    assert client.get(f"{BASE}/{patient.id}", headers=admin_headers).status_code == 200
