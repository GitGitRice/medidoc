"""Anmeldung — Endpunkte.

**Strang C (Steven), noch leer.** Der verbindliche Vertrag steht in
docs/auth-api.md und ist dort schon abgestimmt:

- `POST /auth/login` — formular-kodiert (`OAuth2PasswordRequestForm`),
  Feld `username` enthält die E-Mail. Antwort: `TokenResponse`.
  `401` bei falscher E-Mail *oder* falschem Passwort, bewusst nicht
  unterscheidbar.
- `GET /auth/me` — liefert `UserPublic` zum Token.

Was hier gebraucht wird, liegt schon bereit: `app.core.security` hasht und
prüft Passwörter, `app.modules.users.service` holt den Benutzer aus der
Datenbank. Das JWT-Secret und die Laufzeit stehen in `app.core.config`.

Der Router ist bereits in `app/api/router.py` eingehängt — es kommen nur noch
die beiden Endpunkte dazu.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])
