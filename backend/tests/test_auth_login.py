"""POST /auth/login — ein Test pro Akzeptanzkriterium aus Issue #14.

Der Vertrag steht in docs/auth-api.md; hier wird geprüft, dass der Code ihn
einhält. Der wichtigste Test ist `test_falsches_passwort_und_unbekannte_email_
sind_nicht_unterscheidbar` — er ist der Grund, warum die Meldung an genau einer
Stelle im Code steht.
"""

from datetime import UTC, datetime

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.modules.auth.router import INVALID_CREDENTIALS
from app.modules.users.models import Role

LOGIN_URL = "/auth/login"


def login(client: TestClient, email: str, password: str):
    """Der Request, den auch das Frontend schickt: formular-kodiert."""
    return client.post(LOGIN_URL, data={"username": email, "password": password})


def test_richtige_zugangsdaten_liefern_ein_token(client: TestClient, make_user):
    user = make_user(email="anna.admin@medidoc.test", password="geheim123")

    response = login(client, "anna.admin@medidoc.test", "geheim123")

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"] == {
        "id": user.id,
        "email": "anna.admin@medidoc.test",
        "name": "Anna Admin",
        "role": "admin",
    }


def test_antwort_enthaelt_niemals_den_passwort_hash(client: TestClient, make_user):
    make_user(password="geheim123")

    response = login(client, "anna.admin@medidoc.test", "geheim123")

    assert "password_hash" not in response.text


def test_falsches_passwort_liefert_401(client: TestClient, make_user):
    make_user(password="geheim123")

    response = login(client, "anna.admin@medidoc.test", "falsch")

    assert response.status_code == 401
    assert response.json()["detail"] == INVALID_CREDENTIALS


def test_falsches_passwort_und_unbekannte_email_sind_nicht_unterscheidbar(
    client: TestClient, make_user
):
    """Der Kern des Akzeptanzkriteriums: kein Hinweis darauf, was falsch war."""
    make_user(email="anna.admin@medidoc.test", password="geheim123")

    falsches_passwort = login(client, "anna.admin@medidoc.test", "falsch")
    unbekannte_email = login(client, "gibtsnicht@medidoc.test", "geheim123")

    assert falsches_passwort.status_code == unbekannte_email.status_code == 401
    assert falsches_passwort.json() == unbekannte_email.json()


def test_deaktivierter_benutzer_kann_sich_nicht_anmelden(client: TestClient, make_user):
    make_user(password="geheim123", is_active=False)

    response = login(client, "anna.admin@medidoc.test", "geheim123")

    assert response.status_code == 401
    assert response.json()["detail"] == INVALID_CREDENTIALS


@pytest.mark.parametrize(
    "geschrieben_als",
    ["Anna.Admin@MediDoc.test", "ANNA.ADMIN@MEDIDOC.TEST", "  anna.admin@medidoc.test "],
)
def test_email_ist_case_insensitiv(client: TestClient, make_user, geschrieben_als: str):
    make_user(email="anna.admin@medidoc.test", password="geheim123")

    response = login(client, geschrieben_als, "geheim123")

    assert response.status_code == 200


def test_token_traegt_benutzer_rolle_und_ablaufzeit(client: TestClient, make_user):
    """`sub`, `role`, `exp` — die Form aus docs/auth-api.md."""
    user = make_user(password="geheim123", role=Role.STAFF)

    token = login(client, "anna.admin@medidoc.test", "geheim123").json()["access_token"]
    payload = jwt.decode(
        token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
    )

    assert payload["sub"] == str(user.id)
    assert payload["role"] == "staff"

    laufzeit_minuten = (
        datetime.fromtimestamp(payload["exp"], UTC) - datetime.now(UTC)
    ).total_seconds() / 60
    # Eine Minute Toleranz für die Laufzeit des Tests selbst.
    assert settings.jwt_expire_minutes - 1 <= laufzeit_minuten <= settings.jwt_expire_minutes


def test_token_ist_mit_falschem_secret_nicht_zu_lesen(client: TestClient, make_user):
    """Beweist, dass das Secret wirklich verwendet wird und nicht dekorativ ist."""
    make_user(password="geheim123")

    token = login(client, "anna.admin@medidoc.test", "geheim123").json()["access_token"]

    # Das falsche Secret ist absichtlich lang genug: Ein kurzes loest eine
    # InsecureKeyLengthWarning aus und macht jeden Lauf unnoetig gelb.
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(
            token,
            "ein-anderes-secret-mit-mindestens-32-zeichen",
            algorithms=[settings.jwt_algorithm],
        )
