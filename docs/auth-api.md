# Auth — API-Vertrag

> **Zweck:** Damit Frontend und Backend arbeiten können, bevor die Auth-Endpunkte fertig
> sind. Diese Datei ist die verbindliche Form. Ändert sich hier etwas, wird es hier
> geändert und im Daily gesagt.
>
> Rollenmodell: [ADR-0005](./adr/0005-rollen-admin-und-mitarbeiter.md).
> Entscheidung für echte Auth: [ADR-0003](./adr/0003-echte-authentifizierung.md).

Basis-URL lokal: `http://localhost:8000`

## Kurzfassung

- Anmeldung liefert einen **JWT**, der als `Authorization: Bearer <token>` mitgeschickt wird.
- Der Token liegt im Frontend in `localStorage`.
- Jeder Endpunkt außer `POST /auth/login` verlangt einen gültigen Token.
- Rollen: `admin` und `mitarbeiter`. In Sprint 1 prüft genau ein Endpunkt die Rolle.

## POST /auth/login

Anmeldung. **Formular-kodiert** (`application/x-www-form-urlencoded`), nicht JSON — das
ist die Form, die FastAPI mit `OAuth2PasswordRequestForm` erwartet und die den
*Authorize*-Button in `/docs` funktionieren lässt. Das ist der Grund für diese Wahl: Der
Rest des Teams kann damit geschützte Endpunkte direkt in der Swagger-UI testen.

Das Feld heißt aus historischen Gründen `username`, enthält bei uns aber die **E-Mail**.

**Request**

```
POST /auth/login
Content-Type: application/x-www-form-urlencoded

username=anna.admin@medidoc.test&password=geheim123
```

**Response `200`**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "benutzer": {
    "id": 1,
    "email": "anna.admin@medidoc.test",
    "name": "Anna Admin",
    "rolle": "admin"
  }
}
```

Der Benutzer kommt gleich mit, damit das Frontend nach dem Login keinen zweiten Request
braucht.

**Response `401`** — falsche E-Mail *oder* falsches Passwort, bewusst nicht unterscheidbar:

```json
{ "detail": "E-Mail oder Passwort ist falsch" }
```

## GET /auth/me

Liefert den aktuell angemeldeten Benutzer. Wird vom Frontend beim Laden der Seite benutzt,
um einen gespeicherten Token zu prüfen.

**Request**

```
GET /auth/me
Authorization: Bearer <token>
```

**Response `200`**

```json
{
  "id": 1,
  "email": "anna.admin@medidoc.test",
  "name": "Anna Admin",
  "rolle": "admin"
}
```

**Response `401`** — Token fehlt, ist abgelaufen oder ungültig.

## 401 und 403 sind verschiedene Dinge

Diese Unterscheidung ist für das Frontend wichtig:

| Status | Bedeutung | Was das Frontend tut |
| ------ | --------- | -------------------- |
| `401` | nicht angemeldet, Token fehlt oder abgelaufen | Token verwerfen, zur Login-Seite |
| `403` | angemeldet, aber Rolle reicht nicht | Meldung "Dazu fehlt dir die Berechtigung", **kein** Logout |

Ein `401` wegen abgelaufenem Token ist der Normalfall nach acht Stunden, kein Fehler.

## Der Token

- Verfahren `HS256`, Secret aus `JWT_SECRET` in der `.env`
- Laufzeit **8 Stunden** (eine Praxis-Schicht), kein Refresh-Token
- Payload: `sub` (Benutzer-ID als String), `rolle`, `exp`

Die Rolle steht im Token, damit das Frontend die Oberfläche danach richten kann. Sie wird
im Backend trotzdem bei jeder Prüfung aus der Datenbank gelesen — ein Token, der nach einer
Rollenänderung noch acht Stunden gilt, soll keine alten Rechte mitschleppen.

## Für das Frontend

```js
// Login
const body = new URLSearchParams({ username: email, password });
const res = await fetch("http://localhost:8000/auth/login", {
  method: "POST",
  headers: { "Content-Type": "application/x-www-form-urlencoded" },
  body,
});

// Jeder weitere Request
fetch(url, { headers: { Authorization: `Bearer ${token}` } });
```

`AuthContext` hält `benutzer` und `token`, schreibt den Token nach `localStorage` und
liest ihn beim Start wieder ein — mit einem `GET /auth/me`, um zu prüfen, ob er noch gilt.
`ProtectedRoute` leitet ohne gültigen Benutzer auf `/login` um.

Die Rolle darf benutzt werden, um den Löschen-Button auszublenden. Das ist Bedienkomfort,
keine Absicherung — durchgesetzt wird im Backend.

## Für das Backend

Zwei Dependencies stehen zur Verfügung, sobald der Login steht:

```python
# nur angemeldet
@router.get("/patienten")
def patienten_liste(benutzer: Benutzer = Depends(get_current_user)): ...

# angemeldet und in der erlaubten Rollenmenge
@router.delete("/patienten/{patient_id}")
def patient_loeschen(
    patient_id: int,
    benutzer: Benutzer = Depends(require_rollen(Rolle.ADMIN)),
): ...
```

`require_rollen` prüft gegen eine **Menge** erlaubter Rollen, nicht gegen eine Rangfolge —
Begründung in [ADR-0005](./adr/0005-rollen-admin-und-mitarbeiter.md).

In Sprint 1 benutzt genau ein Endpunkt `require_rollen`: das Löschen eines Patienten. Alle
anderen nehmen `get_current_user`.

## Benutzer-Modell

| Feld | Typ | Hinweis |
| ---- | --- | ------- |
| `id` | int | Primärschlüssel |
| `email` | str | eindeutig, Login-Kennung |
| `name` | str | Anzeigename |
| `passwort_hash` | str | bcrypt, wird **nie** ausgeliefert |
| `rolle` | str | `admin` oder `mitarbeiter` |
| `ist_aktiv` | bool | Standard `true`; inaktive Benutzer können sich nicht anmelden |
| `erstellt_am` | datetime | |

Passwörter werden mit **bcrypt** gehasht (Paket `bcrypt` direkt, nicht `passlib` — passlib
1.7.4 ist unmaintained und bricht gegen bcrypt 4.x).

## Seed-Benutzer

Es gibt keine Selbstregistrierung. Benutzer entstehen über das Seed-Skript:

| E-Mail | Passwort | Rolle |
| ------ | -------- | ----- |
| `anna.admin@medidoc.test` | `geheim123` | `admin` |
| `tom.mitarbeiter@medidoc.test` | `geheim123` | `mitarbeiter` |

Reine Testdaten, wie das ganze Projekt. Für ein Deployment in Sprint 2 müssten sie ersetzt
werden.

## Abhängigkeiten

**Von Infra (`.env`):** `JWT_SECRET`, `DATABASE_URL`. Ein `.env.example` liegt im Repo, die
echte `.env` ist in `.gitignore`.

**Zum Backend-Strang:** Die Auth-Arbeit legt `engine`, `get_session` und die SQLModel-Basis
in `backend/app/db.py` an, weil der Login sie zuerst braucht. Diese Datei gehört danach
beiden Strängen — Patienten-Modelle bauen darauf auf, statt eine zweite Session-Verwaltung
anzulegen.

## Nicht enthalten

Refresh-Token, Passwort-Reset, Selbstregistrierung, "Angemeldet bleiben",
Sperre nach zu vielen Fehlversuchen. Nichts davon ist für die Vorführung nötig.
