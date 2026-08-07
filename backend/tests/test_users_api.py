"""Benutzerverwaltung — Issue #50.

Geprüft wird ausschließlich über HTTP, so wie `test_patients_api.py` es auch
hält: Was ein `admin` über die API tun kann, ist der Vertrag — wie
`users/service.py` das intern löst, darf sich ändern, ohne dass hier ein Test
rot wird.
"""

from fastapi.testclient import TestClient


def test_admin_legt_benutzer_an(client: TestClient, admin_headers):
    response = client.post(
        "/users",
        headers=admin_headers,
        json={
            "email": "neue.kollegin@medidoc.test",
            "name": "Neue Kollegin",
            "password": "geheim123",
            "role": "staff",
        },
    )

    assert response.status_code == 201
    angelegt = response.json()
    assert angelegt["email"] == "neue.kollegin@medidoc.test"
    assert angelegt["name"] == "Neue Kollegin"
    assert angelegt["role"] == "staff"
    assert angelegt["id"] is not None


def test_angelegter_benutzer_kann_sich_anmelden(client: TestClient, admin_headers):
    """Der eigentliche Zweck des Anlegens — das Konto muss benutzbar sein."""
    client.post(
        "/users",
        headers=admin_headers,
        json={
            "email": "neue.kollegin@medidoc.test",
            "name": "Neue Kollegin",
            "password": "geheim123",
            "role": "staff",
        },
    )

    # Der Login nimmt ein Formular, das Feld heißt `username` und enthält die
    # E-Mail (docs/auth-api.md).
    response = client.post(
        "/auth/login",
        data={"username": "neue.kollegin@medidoc.test", "password": "geheim123"},
    )

    assert response.status_code == 200


def test_anlegen_gibt_das_passwort_nicht_zurueck(client: TestClient, admin_headers):
    response = client.post(
        "/users",
        headers=admin_headers,
        json={
            "email": "neue.kollegin@medidoc.test",
            "name": "Neue Kollegin",
            "password": "geheim123",
            "role": "staff",
        },
    )

    assert "password" not in response.json()
    assert "password_hash" not in response.json()


def test_anlegen_mit_vergebener_email_liefert_409(
    client: TestClient, admin_headers, make_user
):
    make_user(email="schon.da@medidoc.test")

    response = client.post(
        "/users",
        headers=admin_headers,
        json={
            "email": "schon.da@medidoc.test",
            "name": "Zweite Anna",
            "password": "geheim123",
            "role": "staff",
        },
    )

    assert response.status_code == 409


def test_anlegen_prueft_die_email_ohne_gross_kleinschreibung(
    client: TestClient, admin_headers, make_user
):
    """Sonst entstünden zwei Konten, von denen eines nie gefunden wird.

    `get_by_email` normalisiert beim Suchen — ein als `Schon.Da@…` angelegtes
    zweites Konto wäre damit still unerreichbar.
    """
    make_user(email="schon.da@medidoc.test")

    response = client.post(
        "/users",
        headers=admin_headers,
        json={
            "email": "Schon.Da@medidoc.test",
            "name": "Zweite Anna",
            "password": "geheim123",
            "role": "staff",
        },
    )

    assert response.status_code == 409


def test_staff_darf_keinen_benutzer_anlegen(client: TestClient, staff_headers):
    response = client.post(
        "/users",
        headers=staff_headers,
        json={
            "email": "neue.kollegin@medidoc.test",
            "name": "Neue Kollegin",
            "password": "geheim123",
            "role": "staff",
        },
    )

    assert response.status_code == 403


def test_anlegen_ohne_token_liefert_401(client: TestClient):
    response = client.post(
        "/users",
        json={
            "email": "neue.kollegin@medidoc.test",
            "name": "Neue Kollegin",
            "password": "geheim123",
            "role": "staff",
        },
    )

    assert response.status_code == 401


def test_admin_deaktiviert_einen_benutzer(
    client: TestClient, admin_headers, make_user
):
    tom = make_user(email="tom.staff@medidoc.test", role="staff")

    response = client.patch(
        f"/users/{tom.id}",
        headers=admin_headers,
        json={"is_active": False},
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_deaktivierter_benutzer_kann_sich_nicht_mehr_anmelden(
    client: TestClient, admin_headers, make_user
):
    """Das eigentliche Akzeptanzkriterium — Deaktivieren muss den Zugang schließen."""
    tom = make_user(
        email="tom.staff@medidoc.test", password="geheim123", role="staff"
    )

    client.patch(
        f"/users/{tom.id}", headers=admin_headers, json={"is_active": False}
    )
    response = client.post(
        "/auth/login",
        data={"username": "tom.staff@medidoc.test", "password": "geheim123"},
    )

    assert response.status_code == 401


def test_admin_aendert_die_rolle(client: TestClient, admin_headers, make_user):
    tom = make_user(email="tom.staff@medidoc.test", role="staff")

    response = client.patch(
        f"/users/{tom.id}", headers=admin_headers, json={"role": "admin"}
    )

    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_neue_rolle_gilt_sofort_fuer_den_bestehenden_token(
    client: TestClient, admin_headers, make_user, auth_headers, make_patient
):
    """Die Rolle wird bei jedem Request aus der Datenbank gelesen.

    Deshalb braucht ein hochgestufter Benutzer keinen neuen Token — geprüft am
    Löschen, der einzigen Stelle in Sprint 1 mit Rollenprüfung.
    """
    tom = make_user(email="tom.staff@medidoc.test", role="staff")
    toms_token = auth_headers(tom)
    patient = make_patient()

    client.patch(f"/users/{tom.id}", headers=admin_headers, json={"role": "admin"})
    response = client.delete(f"/patients/{patient.id}", headers=toms_token)

    assert response.status_code == 204


def test_rollenwechsel_laesst_is_active_unveraendert(
    client: TestClient, admin_headers, make_user
):
    """Ein weggelassenes Feld darf nicht auf seinen Default zurückfallen."""
    tom = make_user(email="tom.staff@medidoc.test", role="staff")
    client.patch(f"/users/{tom.id}", headers=admin_headers, json={"is_active": False})

    response = client.patch(
        f"/users/{tom.id}", headers=admin_headers, json={"role": "admin"}
    )

    assert response.json()["is_active"] is False


def test_staff_darf_keine_rolle_aendern(
    client: TestClient, staff_headers, make_user
):
    tom = make_user(email="anderer@medidoc.test", role="staff")

    response = client.patch(
        f"/users/{tom.id}", headers=staff_headers, json={"role": "admin"}
    )

    assert response.status_code == 403


def test_aendern_eines_unbekannten_benutzers_liefert_404(
    client: TestClient, admin_headers
):
    response = client.patch(
        "/users/9999", headers=admin_headers, json={"is_active": False}
    )

    assert response.status_code == 404


def test_admin_kann_sich_nicht_selbst_deaktivieren(
    client: TestClient, make_user, auth_headers
):
    """Sonst sperrt ein Fehlklick die Praxis aus ihrer eigenen Verwaltung aus."""
    anna = make_user(email="anna.admin@medidoc.test", role="admin")

    response = client.patch(
        f"/users/{anna.id}",
        headers=auth_headers(anna),
        json={"is_active": False},
    )

    assert response.status_code == 409


def test_admin_kann_sich_nicht_selbst_herabstufen(
    client: TestClient, make_user, auth_headers
):
    anna = make_user(email="anna.admin@medidoc.test", role="admin")

    response = client.patch(
        f"/users/{anna.id}",
        headers=auth_headers(anna),
        json={"role": "staff"},
    )

    assert response.status_code == 409


def test_admin_darf_einen_anderen_admin_deaktivieren(
    client: TestClient, admin_headers, make_user
):
    """Die Sperre gilt dem eigenen Konto, nicht der Rolle."""
    kollege = make_user(email="zweiter.admin@medidoc.test", role="admin")

    response = client.patch(
        f"/users/{kollege.id}", headers=admin_headers, json={"is_active": False}
    )

    assert response.status_code == 200


def test_admin_darf_sein_eigenes_konto_sonst_anfassen(
    client: TestClient, make_user, auth_headers
):
    """Ein `PATCH` auf sich selbst, der weder sperrt noch herabstuft, ist erlaubt."""
    anna = make_user(email="anna.admin@medidoc.test", role="admin")

    response = client.patch(
        f"/users/{anna.id}",
        headers=auth_headers(anna),
        json={"role": "admin", "is_active": True},
    )

    assert response.status_code == 200


def test_deaktivieren_loescht_den_benutzer_nicht(
    client: TestClient, admin_headers, make_user, session
):
    """Kein hartes Löschen: Der Audit-Trail verweist auf Benutzer-IDs (ADR-0005)."""
    from app.modules.users.models import User

    tom = make_user(email="tom.staff@medidoc.test", role="staff")

    client.patch(
        f"/users/{tom.id}", headers=admin_headers, json={"is_active": False}
    )

    assert session.get(User, tom.id) is not None
