"""Token-Prüfung und Rollenabsicherung — Issue #15."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import create_access_token
from app.modules.users.models import Role


def test_auth_me_liefert_den_angemeldeten_benutzer(
    client: TestClient, make_user, auth_headers
):
    user = make_user()

    response = client.get("/auth/me", headers=auth_headers(user))

    assert response.status_code == 200
    assert response.json() == {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
    }


def test_auth_me_ohne_token_liefert_401(client: TestClient):
    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_auth_me_mit_ungueltigem_token_liefert_401(client: TestClient):
    response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer kein-gueltiges-jwt"},
    )

    assert response.status_code == 401


def test_auth_me_mit_abgelaufenem_token_liefert_401(
    client: TestClient, make_user
):
    user = make_user()
    token = jwt.encode(
        {
            "sub": str(user.id),
            "role": user.role,
            "exp": datetime.now(UTC) - timedelta(seconds=1),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


def test_auth_me_lehnt_token_ohne_ablaufzeit_ab(client: TestClient, make_user):
    user = make_user()
    token = jwt.encode(
        {"sub": str(user.id), "role": user.role},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


def test_auth_me_lehnt_inzwischen_deaktivierten_benutzer_ab(
    client: TestClient, session, make_user, auth_headers
):
    user = make_user()
    headers = auth_headers(user)
    user.is_active = False
    session.add(user)
    session.commit()

    response = client.get("/auth/me", headers=headers)

    assert response.status_code == 401


@pytest.mark.parametrize(
    ("method", "url", "body"),
    [
        ("GET", "/patients", None),
        (
            "POST",
            "/patients",
            {
                "first_name": "Max",
                "last_name": "Mustermann",
                "date_of_birth": "1980-01-01",
            },
        ),
        ("GET", "/patients/1", None),
        ("PATCH", "/patients/1", {"city": "Hamburg"}),
        ("DELETE", "/patients/1", None),
    ],
)
def test_alle_patienten_endpunkte_verlangen_einen_token(
    client: TestClient, method: str, url: str, body: dict | None
):
    response = client.request(method, url, json=body)

    assert response.status_code == 401


def test_patient_loeschen_prueft_die_aktuelle_rolle_aus_der_datenbank(
    client: TestClient, make_user
):
    user = make_user(role=Role.STAFF)
    token_mit_alter_admin_rolle = create_access_token(user.id, Role.ADMIN)

    response = client.delete(
        "/patients/1",
        headers={"Authorization": f"Bearer {token_mit_alter_admin_rolle}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Dazu fehlt dir die Berechtigung"


def test_staff_darf_patienten_lesen(client: TestClient, make_user, auth_headers):
    staff = make_user(role=Role.STAFF)

    response = client.get("/patients", headers=auth_headers(staff))

    assert response.status_code == 200


def test_admin_darf_patienten_loeschen(client: TestClient, make_user, auth_headers):
    admin = make_user(role=Role.ADMIN)
    headers = auth_headers(admin)
    created = client.post(
        "/patients",
        headers=headers,
        json={
            "first_name": "Max",
            "last_name": "Mustermann",
            "date_of_birth": "1980-01-01",
        },
    )

    response = client.delete(
        f"/patients/{created.json()['id']}",
        headers=headers,
    )

    assert created.status_code == 201
    assert response.status_code == 204
