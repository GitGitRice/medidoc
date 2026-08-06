"""Audit-Trail und Missbrauchserkennung.

Der Trail ist die Stelle, an der eine Unachtsamkeit am teuersten wird: Er läuft
dauerhaft mit und speichert genau die Daten, die nirgends stehen sollen. Die
Tests zu Redaktion und Datensparsamkeit sind deshalb nicht Beiwerk, sondern der
Kern dieser Datei.

Gegen SQLite und den Speicher-Trail — kein Mongo nötig, siehe
`MemoryAuditStore` in app/modules/audit/store.py.
"""

import logging

import pytest
from fastapi.testclient import TestClient

from app.core.logging import REDACTED, JsonFormatter, redact, request_id_var
from app.modules.audit.events import AuditEvent, EventType, Severity
from app.modules.audit.store import MemoryAuditStore
from app.modules.users.models import Role

LOGIN = "/auth/login"
PATIENTEN = "/patients"


def anmelden(client: TestClient, email: str, passwort: str):
    return client.post(LOGIN, data={"username": email, "password": passwort})


def ereignisse(store: MemoryAuditStore, event: EventType) -> list[dict]:
    return [e for e in store.recent(limit=500) if e["event"] == event]


class TestAnmeldeversuche:
    """Das erste ausdrückliche Ziel: Anmeldeversuche protokollieren."""

    def test_erfolgreiche_anmeldung_wird_festgehalten(
        self, client: TestClient, make_user, audit_store
    ):
        user = make_user(email="anna.admin@medidoc.test", password="geheim123")

        anmelden(client, "anna.admin@medidoc.test", "geheim123")

        treffer = ereignisse(audit_store, EventType.LOGIN_SUCCEEDED)
        assert len(treffer) == 1
        assert treffer[0]["email"] == "anna.admin@medidoc.test"
        assert treffer[0]["user_id"] == user.id
        assert treffer[0]["severity"] == Severity.INFO

    def test_fehlversuch_wird_mit_der_versuchten_email_festgehalten(
        self, client: TestClient, make_user, audit_store
    ):
        """Die Antwort verrät nicht, welches Konto gemeint war — der Trail schon.

        Genau dafür ist er da: Ohne die E-Mail wüsste man nur, dass irgendwer
        gescheitert ist, und könnte einen Angriff auf ein bestimmtes Konto nicht
        erkennen.
        """
        make_user(email="anna.admin@medidoc.test", password="geheim123")

        anmelden(client, "anna.admin@medidoc.test", "falsch")

        treffer = ereignisse(audit_store, EventType.LOGIN_FAILED)
        assert len(treffer) == 1
        assert treffer[0]["email"] == "anna.admin@medidoc.test"
        assert treffer[0]["severity"] == Severity.WARNING
        assert treffer[0]["user_id"] is None

    def test_fehlversuch_auf_unbekanntes_konto_wird_auch_festgehalten(
        self, client: TestClient, audit_store
    ):
        anmelden(client, "gibtsnicht@medidoc.test", "egal")

        treffer = ereignisse(audit_store, EventType.LOGIN_FAILED)
        assert len(treffer) == 1
        assert treffer[0]["email"] == "gibtsnicht@medidoc.test"

    def test_email_wird_normalisiert_gezaehlt(
        self, client: TestClient, make_user, audit_store
    ):
        """Sonst liefe ein Angreifer mit wechselnder Schreibweise unter jeder Schwelle durch."""
        make_user(email="anna.admin@medidoc.test", password="geheim123")

        anmelden(client, "ANNA.ADMIN@MEDIDOC.TEST", "falsch")
        anmelden(client, "  Anna.Admin@medidoc.test ", "falsch")

        treffer = ereignisse(audit_store, EventType.LOGIN_FAILED)
        assert {e["email"] for e in treffer} == {"anna.admin@medidoc.test"}


class TestKeineGeheimnisseImTrail:
    """Was nie im Trail stehen darf."""

    def test_passwort_taucht_nirgends_auf(
        self, client: TestClient, make_user, audit_store
    ):
        make_user(email="anna.admin@medidoc.test", password="geheim123")

        anmelden(client, "anna.admin@medidoc.test", "streng-geheimes-passwort")

        assert "streng-geheimes-passwort" not in str(audit_store.recent(limit=500))

    def test_token_taucht_nirgends_auf(
        self, client: TestClient, make_user, auth_headers, audit_store
    ):
        user = make_user()
        headers = auth_headers(user)

        client.get("/auth/me", headers=headers)

        token = headers["Authorization"].removeprefix("Bearer ")
        assert token not in str(audit_store.recent(limit=500))

    def test_patientendaten_tauchen_nicht_auf(
        self, client: TestClient, admin_headers, audit_store
    ):
        """Der Trail nennt `patient:1`, nicht den Menschen dahinter."""
        client.post(
            PATIENTEN,
            json={
                "first_name": "Ungewöhnlichervorname",
                "last_name": "Ungewöhnlichernachname",
                "date_of_birth": "1978-03-14",
                "insurance_number": "X999888777",
            },
            headers=admin_headers,
        )

        trail = str(audit_store.recent(limit=500))
        assert "Ungewöhnlichervorname" not in trail
        assert "Ungewöhnlichernachname" not in trail
        assert "X999888777" not in trail
        assert "patient:" in trail

    def test_geaenderte_felder_werden_benannt_ihre_werte_nicht(
        self, client: TestClient, admin_headers, make_patient, audit_store
    ):
        patient = make_patient()

        client.patch(
            f"{PATIENTEN}/{patient.id}",
            json={"city": "Geheimstadt", "phone": "030 999"},
            headers=admin_headers,
        )

        treffer = ereignisse(audit_store, EventType.PATIENT_UPDATED)
        assert treffer[0]["detail"]["fields"] == ["city", "phone"]
        assert "Geheimstadt" not in str(treffer)

    def test_redact_ersetzt_verraeterische_felder_auch_verschachtelt(self):
        sauber = redact(
            {
                "user": "anna",
                "password": "geheim",
                "nested": {"access_token": "abc", "ok": 1},
            }
        )

        assert sauber == {
            "user": "anna",
            "password": REDACTED,
            "nested": {"access_token": REDACTED, "ok": 1},
        }

    def test_json_formatter_redigiert_zusatzfelder(self):
        record = logging.LogRecord("t", logging.INFO, "f", 1, "msg", None, None)
        record.password = "geheim"  # type: ignore[attr-defined]

        zeile = JsonFormatter().format(record)

        assert "geheim" not in zeile
        assert REDACTED in zeile


class TestPatientenAenderungen:
    """Schreibende Zugriffe auf Patientendaten sind nachvollziehbar."""

    def test_anlegen_wird_festgehalten(
        self, client: TestClient, admin_headers, audit_store
    ):
        antwort = client.post(
            PATIENTEN,
            json={"first_name": "Max", "last_name": "Mustermann", "date_of_birth": "1978-03-14"},
            headers=admin_headers,
        )

        treffer = ereignisse(audit_store, EventType.PATIENT_CREATED)
        assert len(treffer) == 1
        assert treffer[0]["target"] == f"patient:{antwort.json()['id']}"
        assert treffer[0]["user_id"] is not None

    def test_loeschen_wird_festgehalten(
        self, client: TestClient, admin_headers, make_patient, audit_store
    ):
        """Nach dem Löschen ist dieser Eintrag der einzige Beleg."""
        patient = make_patient()

        client.delete(f"{PATIENTEN}/{patient.id}", headers=admin_headers)

        treffer = ereignisse(audit_store, EventType.PATIENT_DELETED)
        assert treffer[0]["target"] == f"patient:{patient.id}"

    def test_lesen_wird_nicht_festgehalten(
        self, client: TestClient, admin_headers, make_patient, audit_store
    ):
        """Sonst ertrinkt der Trail im Normalbetrieb der Übersicht."""
        patient = make_patient()

        client.get(f"{PATIENTEN}/{patient.id}", headers=admin_headers)
        client.get(PATIENTEN, headers=admin_headers)

        assert audit_store.recent(limit=500) == []


class TestEndpunktMissbrauch:
    """Das zweite ausdrückliche Ziel: Auth, Token und Patienten beobachten."""

    def test_abgewiesener_token_wird_festgehalten(
        self, client: TestClient, audit_store
    ):
        client.get(PATIENTEN, headers={"Authorization": "Bearer kein-gueltiges-jwt"})

        treffer = ereignisse(audit_store, EventType.TOKEN_REJECTED)
        assert len(treffer) == 1
        assert treffer[0]["path"] == PATIENTEN
        assert treffer[0]["status"] == 401

    def test_fehlgeschlagener_login_zaehlt_nicht_als_token_missbrauch(
        self, client: TestClient, audit_store
    ):
        """Sonst stünde jeder Fehlversuch doppelt im Trail."""
        anmelden(client, "gibtsnicht@medidoc.test", "egal")

        assert ereignisse(audit_store, EventType.TOKEN_REJECTED) == []
        assert len(ereignisse(audit_store, EventType.LOGIN_FAILED)) == 1

    def test_abgewehrter_zugriff_wird_mit_benutzer_festgehalten(
        self, client: TestClient, staff_headers, make_patient, audit_store
    ):
        patient = make_patient()

        client.delete(f"{PATIENTEN}/{patient.id}", headers=staff_headers)

        treffer = ereignisse(audit_store, EventType.FORBIDDEN)
        assert len(treffer) == 1
        assert treffer[0]["user_id"] is not None
        assert treffer[0]["target"] == f"patient:{patient.id}"

    def test_zugriff_auf_unbekannte_id_wird_festgehalten(
        self, client: TestClient, admin_headers, audit_store
    ):
        client.get(f"{PATIENTEN}/999999", headers=admin_headers)

        treffer = ereignisse(audit_store, EventType.NOT_FOUND)
        assert treffer[0]["target"] == "patient:999999"

    def test_health_wird_nicht_protokolliert(self, client: TestClient, audit_store):
        client.get("/health")

        assert audit_store.recent(limit=500) == []


class TestErkennung:
    """Die Schwellen schlagen an — und blockieren nichts."""

    def test_wiederholte_fehlversuche_loesen_eine_warnung_aus(
        self, client: TestClient, make_user, audit_store, monkeypatch
    ):
        from app.core.config import settings

        monkeypatch.setattr(settings, "abuse_failed_logins_per_email", 3)
        make_user(email="anna.admin@medidoc.test", password="geheim123")

        for _ in range(3):
            anmelden(client, "anna.admin@medidoc.test", "falsch")

        verdacht = ereignisse(audit_store, EventType.SUSPICIOUS)
        assert len(verdacht) == 1
        assert verdacht[0]["detail"]["rule"] == "brute_force_email"
        assert verdacht[0]["detail"]["count"] == 3
        assert verdacht[0]["email"] == "anna.admin@medidoc.test"

    def test_unter_der_schwelle_passiert_nichts(
        self, client: TestClient, make_user, audit_store, monkeypatch
    ):
        from app.core.config import settings

        monkeypatch.setattr(settings, "abuse_failed_logins_per_email", 3)
        make_user(email="anna.admin@medidoc.test", password="geheim123")

        for _ in range(2):
            anmelden(client, "anna.admin@medidoc.test", "falsch")

        assert ereignisse(audit_store, EventType.SUSPICIOUS) == []

    def test_die_warnung_kommt_einmal_und_nicht_bei_jedem_weiteren_versuch(
        self, client: TestClient, make_user, audit_store, monkeypatch
    ):
        """Sonst liefe der Trail mit Wiederholungen desselben Befunds voll."""
        from app.core.config import settings

        monkeypatch.setattr(settings, "abuse_failed_logins_per_email", 3)
        make_user(email="anna.admin@medidoc.test", password="geheim123")

        for _ in range(8):
            anmelden(client, "anna.admin@medidoc.test", "falsch")

        assert len(ereignisse(audit_store, EventType.SUSPICIOUS)) == 1

    def test_es_wird_niemals_blockiert(
        self, client: TestClient, make_user, audit_store, monkeypatch
    ):
        """Die ausdrückliche Entscheidung: erkennen, nicht sperren.

        Nach beliebig vielen Fehlversuchen meldet sich das richtige Passwort
        weiterhin an — kein 429, keine Sperre.
        """
        from app.core.config import settings

        monkeypatch.setattr(settings, "abuse_failed_logins_per_email", 3)
        make_user(email="anna.admin@medidoc.test", password="geheim123")

        for _ in range(10):
            antwort = anmelden(client, "anna.admin@medidoc.test", "falsch")
            assert antwort.status_code == 401

        assert anmelden(client, "anna.admin@medidoc.test", "geheim123").status_code == 200

    def test_id_enumeration_wird_erkannt(
        self, client: TestClient, admin_headers, audit_store, monkeypatch
    ):
        """Der Fall, der bei Patientendaten wirklich zählt."""
        from app.core.config import settings

        monkeypatch.setattr(settings, "abuse_not_found_per_user", 4)

        for patient_id in range(900, 904):
            client.get(f"{PATIENTEN}/{patient_id}", headers=admin_headers)

        verdacht = ereignisse(audit_store, EventType.SUSPICIOUS)
        assert len(verdacht) == 1
        assert verdacht[0]["detail"]["rule"] == "id_enumeration"

    def test_ein_verdacht_loest_keinen_weiteren_verdacht_aus(self, audit_store, monkeypatch):
        """Wächter gegen eine Endlosschleife in der Erkennung."""
        from app.modules.audit import service

        service.record(EventType.SUSPICIOUS, detail={"rule": "test"})

        assert len(ereignisse(audit_store, EventType.SUSPICIOUS)) == 1


class TestMonitoringEndpunkt:
    """GET /monitoring/* — nur für admin."""

    def test_admin_sieht_die_ereignisse(
        self, client: TestClient, admin_headers, audit_store
    ):
        client.get(f"{PATIENTEN}/999999", headers=admin_headers)

        antwort = client.get("/monitoring/ereignisse", headers=admin_headers)

        assert antwort.status_code == 200
        assert any(e["event"] == EventType.NOT_FOUND for e in antwort.json())

    def test_filter_nach_schweregrad(
        self, client: TestClient, admin_headers, audit_store
    ):
        client.post(
            PATIENTEN,
            json={"first_name": "Max", "last_name": "Mustermann", "date_of_birth": "1978-03-14"},
            headers=admin_headers,
        )
        client.get(f"{PATIENTEN}/999999", headers=admin_headers)

        antwort = client.get(
            "/monitoring/ereignisse", params={"severity": "warning"}, headers=admin_headers
        )

        arten = {e["event"] for e in antwort.json()}
        assert EventType.NOT_FOUND in arten
        assert EventType.PATIENT_CREATED not in arten

    def test_staff_darf_nicht_hineinsehen(self, client: TestClient, staff_headers):
        """Wer den Trail liest, sieht auch, welche Konten es gibt."""
        antwort = client.get("/monitoring/ereignisse", headers=staff_headers)

        assert antwort.status_code == 403

    def test_ohne_token_kein_zugriff(self, client: TestClient):
        assert client.get("/monitoring/ereignisse").status_code == 401

    def test_regeln_sind_nachsehbar(self, client: TestClient, admin_headers):
        antwort = client.get("/monitoring/regeln", headers=admin_headers)

        assert antwort.status_code == 200
        namen = {regel["name"] for regel in antwort.json()["rules"]}
        assert namen == {
            "brute_force_email",
            "brute_force_ip",
            "token_probing",
            "privilege_probing",
            "id_enumeration",
        }


class TestAusfallsicherheit:
    """Protokollieren darf nie einen Request kippen."""

    def test_ein_kaputter_trail_bricht_den_request_nicht(
        self, client: TestClient, make_user, monkeypatch
    ):
        """Wenn Mongo hakt, soll die Praxis trotzdem arbeiten können."""
        from app.modules.audit import store as store_modul

        class KaputterStore:
            def record(self, event):
                raise RuntimeError("Mongo ist weg")

            def count_since(self, *args, **kwargs):
                raise RuntimeError("Mongo ist weg")

            def recent(self, *args, **kwargs):
                raise RuntimeError("Mongo ist weg")

        make_user(email="anna.admin@medidoc.test", password="geheim123")
        store_modul.set_store(KaputterStore())

        antwort = anmelden(client, "anna.admin@medidoc.test", "geheim123")

        assert antwort.status_code == 200

    def test_mongo_store_schluckt_schreibfehler(self, caplog):
        """`MongoAuditStore.record` fängt selbst, was pymongo wirft."""
        from app.modules.audit.store import MongoAuditStore

        store = MongoAuditStore.__new__(MongoAuditStore)

        class KaputteCollection:
            def insert_one(self, _dokument):
                raise RuntimeError("keine Verbindung")

        store._collection = KaputteCollection()  # type: ignore[attr-defined]

        with caplog.at_level(logging.WARNING):
            store.record(AuditEvent.build(EventType.LOGIN_FAILED, email="a@b.test"))

        assert "nicht geschrieben" in caplog.text


class TestAnfrageKennung:
    """Eine Kennung, die Logzeile, Audit-Eintrag und Antwort verbindet."""

    def test_jede_antwort_traegt_eine_kennung(self, client: TestClient):
        antwort = client.get("/health")

        assert len(antwort.headers["X-Request-ID"]) == 32

    def test_zwei_anfragen_bekommen_verschiedene_kennungen(self, client: TestClient):
        erste = client.get("/health").headers["X-Request-ID"]
        zweite = client.get("/health").headers["X-Request-ID"]

        assert erste != zweite

    def test_das_audit_ereignis_traegt_dieselbe_kennung_wie_die_antwort(
        self, client: TestClient, admin_headers, audit_store
    ):
        antwort = client.get(f"{PATIENTEN}/999999", headers=admin_headers)

        treffer = ereignisse(audit_store, EventType.NOT_FOUND)
        assert treffer[0]["request_id"] == antwort.headers["X-Request-ID"]

    def test_die_kennung_leckt_nicht_in_den_naechsten_request(self, client: TestClient):
        """Der ContextVar muss auch dann zurückgesetzt werden, wenn es kracht."""
        client.get("/health")

        assert request_id_var.get() is None


@pytest.mark.parametrize(
    ("event", "erwartet"),
    [
        (EventType.LOGIN_SUCCEEDED, Severity.INFO),
        (EventType.PATIENT_CREATED, Severity.INFO),
        (EventType.LOGIN_FAILED, Severity.WARNING),
        (EventType.TOKEN_REJECTED, Severity.WARNING),
        (EventType.FORBIDDEN, Severity.WARNING),
        (EventType.NOT_FOUND, Severity.WARNING),
    ],
)
def test_schweregrad_haengt_am_ereignistyp(event: EventType, erwartet: Severity):
    assert AuditEvent.build(event).severity is erwartet


def test_der_trail_ist_nur_lesbar(client: TestClient, admin_headers):
    """Ein Audit-Trail, den man über die API löschen kann, ist keiner."""
    for methode in ("post", "put", "patch", "delete"):
        antwort = client.request(methode, "/monitoring/ereignisse", headers=admin_headers)
        assert antwort.status_code == 405, methode


def test_rollen_sind_unveraendert():
    """Wächter: Das Monitoring darf die bestehenden Rollen nicht erweitert haben."""
    assert {r.value for r in Role} == {"admin", "staff"}
