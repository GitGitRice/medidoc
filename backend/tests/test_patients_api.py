"""Die Patienten-Endpunkte — ein Test pro Akzeptanzkriterium.

Der Vertrag steht in docs/patients-api.md; hier wird geprüft, dass der Code ihn
einhält. Gegliedert nach Endpunkt, in der Reihenfolge, in der die Kriterien
aufgeschrieben wurden.

Die Absicherung selbst (kein Token → `401`, falsche Rolle → `403`) prüft
`test_auth_authorization.py` für alle Routen auf einmal. Hier steht sie nur
dort, wo sie zum Verhalten des Endpunkts gehört — beim Löschen.

**Hinweis zu SQLite:** Die Tests laufen gegen SQLite im Speicher, produktiv
läuft Postgres. `LIKE` ignoriert in SQLite die Groß-/Kleinschreibung nur bei
ASCII-Zeichen. Die Tests zur Schreibweise benutzen deshalb bewusst
ASCII-Namen — ein Test mit "Özdemir" wäre hier grün und sagte trotzdem nichts
über die Datenbank aus, gegen die die Anwendung wirklich läuft.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient

BASE = "/patienten"

PFLICHTFELDER = {
    "first_name": "Max",
    "last_name": "Mustermann",
    "date_of_birth": "1978-03-14",
}


class TestPatientLesen:
    """GET /patienten/{id}"""

    def test_liefert_den_patienten_zur_id(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient(first_name="Erika", last_name="Musterfrau")

        response = client.get(f"{BASE}/{patient.id}", headers=admin_headers)

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == patient.id
        assert body["first_name"] == "Erika"
        assert body["last_name"] == "Musterfrau"

    def test_liefert_alle_stammdaten_und_die_zeitstempel(
        self, client: TestClient, admin_headers, make_patient
    ):
        """Die Detailansicht ist die vollständige, nicht die schmale Form."""
        patient = make_patient(city="Berlin", insurance_number="A123456789")

        body = client.get(f"{BASE}/{patient.id}", headers=admin_headers).json()

        assert body["city"] == "Berlin"
        assert body["insurance_number"] == "A123456789"
        assert body["created_at"] and body["updated_at"]
        # Nicht gesetzte Felder kommen als null, nicht als fehlender Schlüssel.
        assert body["notes"] is None

    def test_unbekannte_id_liefert_404_mit_verstaendlicher_meldung(
        self, client: TestClient, admin_headers
    ):
        response = client.get(f"{BASE}/999999", headers=admin_headers)

        assert response.status_code == 404
        body = response.json()
        assert body["status"] == 404
        # Die Meldung nennt die gesuchte ID — sonst steht im Frontend-Log nur,
        # dass irgendein Patient nicht gefunden wurde.
        assert body["message"] == "Patient mit der ID 999999 wurde nicht gefunden"


class TestPatientenListe:
    """GET /patienten"""

    def test_liefert_alle_patienten(
        self, client: TestClient, admin_headers, make_patient
    ):
        make_patient(first_name="Max", last_name="Mustermann")
        make_patient(first_name="Erika", last_name="Musterfrau")
        make_patient(first_name="Jonas", last_name="Weber")

        response = client.get(BASE, headers=admin_headers)

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 3
        assert len(body["items"]) == 3

    def test_ist_nach_nachname_und_vorname_sortiert(
        self, client: TestClient, admin_headers, make_patient
    ):
        make_patient(first_name="Lena", last_name="Weber")
        make_patient(first_name="Anton", last_name="Weber")
        make_patient(first_name="Bea", last_name="Albrecht")

        items = client.get(BASE, headers=admin_headers).json()["items"]

        assert [(p["last_name"], p["first_name"]) for p in items] == [
            ("Albrecht", "Bea"),
            ("Weber", "Anton"),
            ("Weber", "Lena"),
        ]

    def test_suche_filtert_nach_nachname(
        self, client: TestClient, admin_headers, make_patient
    ):
        make_patient(first_name="Max", last_name="Mustermann")
        make_patient(first_name="Jonas", last_name="Weber")

        body = client.get(
            BASE, params={"suche": "mustermann"}, headers=admin_headers
        ).json()

        assert body["total"] == 1
        assert body["items"][0]["last_name"] == "Mustermann"

    def test_suche_filtert_nach_vorname(
        self, client: TestClient, admin_headers, make_patient
    ):
        make_patient(first_name="Max", last_name="Mustermann")
        make_patient(first_name="Jonas", last_name="Weber")

        body = client.get(BASE, params={"suche": "jonas"}, headers=admin_headers).json()

        assert body["total"] == 1
        assert body["items"][0]["first_name"] == "Jonas"

    @pytest.mark.parametrize(
        "geschrieben_als", ["mustermann", "MUSTERMANN", "MuStErMaNn", "musTER"]
    )
    def test_suche_ignoriert_gross_und_kleinschreibung(
        self, client: TestClient, admin_headers, make_patient, geschrieben_als: str
    ):
        make_patient(first_name="Max", last_name="Mustermann")

        body = client.get(
            BASE, params={"suche": geschrieben_als}, headers=admin_headers
        ).json()

        assert body["total"] == 1

    def test_suche_findet_auch_teile_des_vornamens_unabhaengig_von_der_schreibweise(
        self, client: TestClient, admin_headers, make_patient
    ):
        make_patient(first_name="Friedrich", last_name="Hartmann")

        body = client.get(
            BASE, params={"suche": "FRIED"}, headers=admin_headers
        ).json()

        assert body["total"] == 1

    def test_mehrere_woerter_werden_und_verknuepft(
        self, client: TestClient, admin_headers, make_patient
    ):
        """Reihenfolge egal — "lena weber" und "weber lena" sind dasselbe."""
        make_patient(first_name="Lena", last_name="Weber")
        make_patient(first_name="Anton", last_name="Weber")

        vorwaerts = client.get(
            BASE, params={"suche": "lena weber"}, headers=admin_headers
        ).json()
        rueckwaerts = client.get(
            BASE, params={"suche": "weber lena"}, headers=admin_headers
        ).json()

        assert vorwaerts["total"] == rueckwaerts["total"] == 1
        assert vorwaerts["items"] == rueckwaerts["items"]

    def test_leeres_ergebnis_liefert_leere_liste_und_keinen_fehler(
        self, client: TestClient, admin_headers, make_patient
    ):
        """Kein Treffer ist ein gültiges Ergebnis, kein 404."""
        make_patient(first_name="Max", last_name="Mustermann")

        response = client.get(
            BASE, params={"suche": "gibtesnicht"}, headers=admin_headers
        )

        assert response.status_code == 200
        assert response.json()["items"] == []
        assert response.json()["total"] == 0

    def test_leere_datenbank_liefert_leere_liste(
        self, client: TestClient, admin_headers
    ):
        response = client.get(BASE, headers=admin_headers)

        assert response.status_code == 200
        assert response.json() == {"items": [], "total": 0, "limit": 25, "offset": 0}

    def test_leere_suche_verhaelt_sich_wie_gar_keine(
        self, client: TestClient, admin_headers, make_patient
    ):
        make_patient()

        ohne = client.get(BASE, headers=admin_headers).json()
        leer = client.get(BASE, params={"suche": ""}, headers=admin_headers).json()

        assert ohne == leer

    def test_prozentzeichen_sucht_sich_selbst_und_nicht_alles(
        self, client: TestClient, admin_headers, make_patient
    ):
        """`%` ist in LIKE ein Platzhalter und muss maskiert werden."""
        make_patient(first_name="Max", last_name="Mustermann")

        body = client.get(BASE, params={"suche": "%"}, headers=admin_headers).json()

        assert body["total"] == 0

    def test_total_zaehlt_alle_treffer_die_seite_nur_ihren_ausschnitt(
        self, client: TestClient, admin_headers, make_patient
    ):
        for nummer in range(5):
            make_patient(first_name=f"Kind{nummer}", last_name="Weber")

        body = client.get(
            BASE, params={"limit": 2, "offset": 2}, headers=admin_headers
        ).json()

        assert body["total"] == 5
        assert len(body["items"]) == 2
        assert body["limit"] == 2
        assert body["offset"] == 2

    def test_zu_grosses_limit_wird_abgelehnt(self, client: TestClient, admin_headers):
        response = client.get(BASE, params={"limit": 1000}, headers=admin_headers)

        assert response.status_code == 422
        assert response.json()["errors"][0]["field"] == "limit"

    def test_listenzeile_bleibt_schmal(
        self, client: TestClient, admin_headers, make_patient
    ):
        """Die Übersicht liefert bewusst nicht alle Felder."""
        make_patient(city="Berlin", notes="Nicht in der Liste")

        zeile = client.get(BASE, headers=admin_headers).json()["items"][0]

        assert set(zeile) == {
            "id",
            "first_name",
            "last_name",
            "date_of_birth",
            "insurance_number",
        }


class TestPatientAnlegen:
    """POST /patienten"""

    def test_legt_den_patienten_an_und_liefert_ihn_mit_id(
        self, client: TestClient, admin_headers
    ):
        response = client.post(BASE, json=PFLICHTFELDER, headers=admin_headers)

        body = response.json()
        assert isinstance(body["id"], int)
        assert body["first_name"] == "Max"
        assert body["last_name"] == "Mustermann"
        assert body["date_of_birth"] == "1978-03-14"

    def test_antwortet_mit_201(self, client: TestClient, admin_headers):
        response = client.post(BASE, json=PFLICHTFELDER, headers=admin_headers)

        assert response.status_code == 201

    def test_der_angelegte_patient_ist_danach_abrufbar(
        self, client: TestClient, admin_headers
    ):
        """Beweist, dass wirklich gespeichert und nicht nur zurückgespiegelt wird."""
        angelegt = client.post(BASE, json=PFLICHTFELDER, headers=admin_headers).json()

        response = client.get(f"{BASE}/{angelegt['id']}", headers=admin_headers)

        assert response.status_code == 200
        assert response.json() == angelegt

    def test_uebernimmt_auch_die_optionalen_felder(
        self, client: TestClient, admin_headers
    ):
        response = client.post(
            BASE,
            json={
                **PFLICHTFELDER,
                "email": "max.mustermann@example.test",
                "phone": "030 1234567",
                "street": "Hauptstraße 12",
                "postal_code": "10115",
                "city": "Berlin",
                "insurance_provider": "AOK Nordost",
                "insurance_number": "A123456789",
                "insurance_type": "statutory",
                "notes": "Allergie gegen Penicillin.",
            },
            headers=admin_headers,
        )

        assert response.status_code == 201
        assert response.json()["insurance_type"] == "statutory"
        assert response.json()["city"] == "Berlin"

    def test_nur_die_pflichtfelder_reichen(self, client: TestClient, admin_headers):
        """Ein Patient ohne Kontakt und ohne Versicherung ist gültig."""
        response = client.post(BASE, json=PFLICHTFELDER, headers=admin_headers)

        assert response.status_code == 201
        assert response.json()["phone"] is None
        assert response.json()["insurance_number"] is None

    @pytest.mark.parametrize("fehlendes_feld", ["first_name", "last_name", "date_of_birth"])
    def test_fehlendes_pflichtfeld_liefert_422_und_nennt_das_feld(
        self, client: TestClient, admin_headers, fehlendes_feld: str
    ):
        unvollstaendig = {k: v for k, v in PFLICHTFELDER.items() if k != fehlendes_feld}

        response = client.post(BASE, json=unvollstaendig, headers=admin_headers)

        assert response.status_code == 422
        body = response.json()
        assert body["status"] == 422
        # Der Feldname steht in der Meldung *und* maschinenlesbar in `errors`.
        assert body["message"] == f"Pflichtfeld fehlt: {fehlendes_feld}"
        assert body["errors"] == [
            {"field": fehlendes_feld, "message": "Feld ist erforderlich"}
        ]

    def test_mehrere_fehlende_pflichtfelder_werden_alle_genannt(
        self, client: TestClient, admin_headers
    ):
        response = client.post(BASE, json={}, headers=admin_headers)

        assert response.status_code == 422
        body = response.json()
        assert body["message"] == (
            "Pflichtfelder fehlen: first_name, last_name, date_of_birth"
        )
        assert [fehler["field"] for fehler in body["errors"]] == [
            "first_name",
            "last_name",
            "date_of_birth",
        ]

    def test_leerer_name_liefert_422(self, client: TestClient, admin_headers):
        response = client.post(
            BASE, json={**PFLICHTFELDER, "first_name": "   "}, headers=admin_headers
        )

        assert response.status_code == 422
        assert response.json()["errors"] == [
            {"field": "first_name", "message": "darf nicht leer sein"}
        ]

    def test_geburtsdatum_in_der_zukunft_liefert_422(
        self, client: TestClient, admin_headers
    ):
        response = client.post(
            BASE,
            json={**PFLICHTFELDER, "date_of_birth": "2099-01-01"},
            headers=admin_headers,
        )

        assert response.status_code == 422
        assert response.json()["errors"] == [
            {"field": "date_of_birth", "message": "darf nicht in der Zukunft liegen"}
        ]

    def test_unlesbares_datum_liefert_422(self, client: TestClient, admin_headers):
        response = client.post(
            BASE,
            json={**PFLICHTFELDER, "date_of_birth": "14.03.1978"},
            headers=admin_headers,
        )

        assert response.status_code == 422
        assert response.json()["errors"][0]["field"] == "date_of_birth"

    def test_name_wird_getrimmt(self, client: TestClient, admin_headers):
        response = client.post(
            BASE, json={**PFLICHTFELDER, "first_name": "  Max  "}, headers=admin_headers
        )

        assert response.json()["first_name"] == "Max"

    def test_doppelte_versichertennummer_liefert_409(
        self, client: TestClient, admin_headers, make_patient
    ):
        make_patient(insurance_number="A123456789")

        response = client.post(
            BASE,
            json={**PFLICHTFELDER, "insurance_number": "A123456789"},
            headers=admin_headers,
        )

        assert response.status_code == 409
        body = response.json()
        assert body["status"] == 409
        assert "A123456789" in body["message"]


class TestPatientAendern:
    """PATCH /patienten/{id}"""

    def test_nur_mitgeschickte_felder_werden_geaendert(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient(
            first_name="Max",
            last_name="Mustermann",
            city="Berlin",
            phone="030 1234567",
        )

        client.patch(
            f"{BASE}/{patient.id}", json={"city": "Hamburg"}, headers=admin_headers
        )

        danach = client.get(f"{BASE}/{patient.id}", headers=admin_headers).json()
        assert danach["city"] == "Hamburg"
        assert danach["first_name"] == "Max"
        assert danach["last_name"] == "Mustermann"
        assert danach["phone"] == "030 1234567"

    def test_liefert_den_aktualisierten_patienten_zurueck(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient(city="Berlin")

        response = client.patch(
            f"{BASE}/{patient.id}", json={"city": "Hamburg"}, headers=admin_headers
        )

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == patient.id
        assert body["city"] == "Hamburg"
        # Die ganze Form, nicht nur das geänderte Feld.
        assert body["last_name"] == "Mustermann"

    def test_updated_at_wandert_mit(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()
        vorher = client.get(f"{BASE}/{patient.id}", headers=admin_headers).json()

        nachher = client.patch(
            f"{BASE}/{patient.id}", json={"city": "Hamburg"}, headers=admin_headers
        ).json()

        assert nachher["updated_at"] != vorher["updated_at"]
        assert nachher["created_at"] == vorher["created_at"]

    def test_unbekannte_id_liefert_404(self, client: TestClient, admin_headers):
        response = client.patch(
            f"{BASE}/999999", json={"city": "Hamburg"}, headers=admin_headers
        )

        assert response.status_code == 404
        assert response.json()["status"] == 404
        assert response.json()["message"] == (
            "Patient mit der ID 999999 wurde nicht gefunden"
        )

    def test_leerer_rumpf_aendert_nichts(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient(city="Berlin")

        response = client.patch(f"{BASE}/{patient.id}", json={}, headers=admin_headers)

        assert response.status_code == 200
        assert response.json()["city"] == "Berlin"

    def test_optionales_feld_laesst_sich_leeren(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient(phone="030 1234567")

        response = client.patch(
            f"{BASE}/{patient.id}", json={"phone": None}, headers=admin_headers
        )

        assert response.json()["phone"] is None

    def test_pflichtfeld_auf_null_liefert_422(
        self, client: TestClient, admin_headers, make_patient
    ):
        """Sonst schlüge erst die Datenbank zu — mit einem 500 statt einem 422."""
        patient = make_patient()

        response = client.patch(
            f"{BASE}/{patient.id}", json={"last_name": None}, headers=admin_headers
        )

        assert response.status_code == 422
        assert response.json()["errors"] == [
            {"field": "last_name", "message": "darf nicht auf null gesetzt werden"}
        ]

    def test_eigene_versichertennummer_bleibt_erlaubt(
        self, client: TestClient, admin_headers, make_patient
    ):
        """Ein Patient darf nicht mit sich selbst kollidieren."""
        patient = make_patient(insurance_number="A123456789")

        response = client.patch(
            f"{BASE}/{patient.id}",
            json={"insurance_number": "A123456789"},
            headers=admin_headers,
        )

        assert response.status_code == 200

    def test_fremde_versichertennummer_liefert_409(
        self, client: TestClient, admin_headers, make_patient
    ):
        make_patient(first_name="Erika", insurance_number="A123456789")
        eigener = make_patient(first_name="Max", insurance_number="B987654321")

        response = client.patch(
            f"{BASE}/{eigener.id}",
            json={"insurance_number": "A123456789"},
            headers=admin_headers,
        )

        assert response.status_code == 409

    def test_unbekannte_id_wird_vor_der_nummernpruefung_beantwortet(
        self, client: TestClient, admin_headers, make_patient
    ):
        """404 schlägt 409 — der Patient existiert ja gar nicht."""
        make_patient(insurance_number="A123456789")

        response = client.patch(
            f"{BASE}/999999",
            json={"insurance_number": "A123456789"},
            headers=admin_headers,
        )

        assert response.status_code == 404


class TestPatientLoeschen:
    """DELETE /patienten/{id}"""

    def test_loescht_den_patienten_und_liefert_204(
        self, client: TestClient, admin_headers, make_patient
    ):
        patient = make_patient()

        response = client.delete(f"{BASE}/{patient.id}", headers=admin_headers)

        assert response.status_code == 204
        assert response.content == b""
        assert (
            client.get(f"{BASE}/{patient.id}", headers=admin_headers).status_code == 404
        )

    def test_loescht_nur_den_gemeinten_patienten(
        self, client: TestClient, admin_headers, make_patient
    ):
        opfer = make_patient(first_name="Max")
        rest = make_patient(first_name="Erika")

        client.delete(f"{BASE}/{opfer.id}", headers=admin_headers)

        assert client.get(f"{BASE}/{rest.id}", headers=admin_headers).status_code == 200
        assert client.get(BASE, headers=admin_headers).json()["total"] == 1

    def test_unbekannte_id_liefert_404(self, client: TestClient, admin_headers):
        response = client.delete(f"{BASE}/999999", headers=admin_headers)

        assert response.status_code == 404
        assert response.json()["status"] == 404
        assert response.json()["message"] == (
            "Patient mit der ID 999999 wurde nicht gefunden"
        )

    def test_zweimaliges_loeschen_ist_kein_serverfehler(
        self, client: TestClient, admin_headers, make_patient
    ):
        """Der zweite Aufruf findet nichts mehr — 404, nicht 500."""
        patient = make_patient()

        erster = client.delete(f"{BASE}/{patient.id}", headers=admin_headers)
        zweiter = client.delete(f"{BASE}/{patient.id}", headers=admin_headers)

        assert erster.status_code == 204
        # 404 und ausdrücklich nichts aus dem 5xx-Bereich.
        assert zweiter.status_code == 404

    def test_staff_darf_nicht_loeschen(
        self, client: TestClient, staff_headers, make_patient
    ):
        """Die einzige Stelle im Sprint 1, die eine Rolle prüft (ADR-0005)."""
        patient = make_patient()

        response = client.delete(f"{BASE}/{patient.id}", headers=staff_headers)

        assert response.status_code == 403
        assert response.json()["message"] == "Dazu fehlt dir die Berechtigung"
        # Der abgewiesene Aufruf darf auch nichts angefangen haben.
        assert (
            client.get(f"{BASE}/{patient.id}", headers=staff_headers).status_code == 200
        )


class TestFehlerformat:
    """Jede Fehlerantwort hat dieselbe Form — siehe app/core/errors.py."""

    def test_jeder_fehler_traegt_status_und_message(
        self, client: TestClient, admin_headers, make_patient
    ):
        make_patient(insurance_number="A123456789")

        antworten = [
            client.get(f"{BASE}/999999", headers=admin_headers),
            client.post(BASE, json={}, headers=admin_headers),
            client.post(
                BASE,
                json={**PFLICHTFELDER, "insurance_number": "A123456789"},
                headers=admin_headers,
            ),
            client.get(BASE),  # ohne Token
        ]

        for antwort in antworten:
            body = antwort.json()
            assert body["status"] == antwort.status_code, antwort.text
            assert isinstance(body["message"], str) and body["message"], antwort.text

    def test_detail_bleibt_fuer_bestandscode_erhalten(
        self, client: TestClient, admin_headers
    ):
        """Solange das Frontend `detail` liest, bleibt es stehen."""
        response = client.get(f"{BASE}/999999", headers=admin_headers)

        assert response.json()["detail"] == response.json()["message"]

    def test_unbekannte_adresse_antwortet_deutsch(self, client: TestClient):
        """Auch der Fall, den nicht wir auslösen, sondern das Framework."""
        response = client.get("/gibtesnicht")

        assert response.status_code == 404
        assert response.json() == {
            "status": 404,
            "message": "Diese Adresse gibt es nicht",
            "detail": "Not Found",
        }

    def test_fehlender_token_liefert_401_mit_header(self, client: TestClient):
        """Der WWW-Authenticate-Header darf im eigenen Format nicht verlorengehen."""
        response = client.get(BASE)

        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"
        assert response.json()["message"] == "Anmeldung erforderlich"


def test_die_gepruefte_route_existiert_wirklich(client: TestClient, admin_headers):
    """Wächter: Ein Tippfehler in BASE würde sonst überall 404 liefern.

    Genau die Sorte Fehler, die eine ganze Testdatei still grün aussehen lässt,
    wenn sie nur auf Fehlerfälle prüft.
    """
    assert client.get(BASE, headers=admin_headers).status_code == 200


def test_das_datum_im_testkopf_passt_zum_modell():
    """Stellt sicher, dass PFLICHTFELDER ein gültiges Geburtsdatum trägt."""
    assert date.fromisoformat(PFLICHTFELDER["date_of_birth"]) < date.today()
