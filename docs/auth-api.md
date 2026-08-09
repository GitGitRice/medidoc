# Auth — API-Vertrag

> **Zweck:** Damit Frontend und Backend arbeiten können, bevor die Auth-Endpunkte fertig
> sind. Diese Datei ist die verbindliche Form. Ändert sich hier etwas, wird es hier
> geändert und im Daily gesagt.
>
> **Sprache:** Code und API sind englisch, deutsch ist nur die Oberfläche im Frontend.
> JSON-Keys und Rollenwerte sind also englisch.
>
> Rollenmodell: [ADR-0005](./adr/0005-rollen-admin-und-staff.md).
> Entscheidung für echte Auth: [ADR-0003](./adr/0003-echte-authentifizierung.md).

Basis-URL lokal: `http://localhost:8000`

## Kurzfassung

- Anmeldung liefert einen **JWT**, der als `Authorization: Bearer <token>` mitgeschickt wird.
- Der Token liegt im Frontend in `localStorage`.
- Jeder Endpunkt außer `POST /auth/login` verlangt einen gültigen Token.
- Rollen: `admin` und `staff`. In Sprint 1 prüft genau ein Endpunkt die Rolle.

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
  "user": {
    "id": 1,
    "email": "anna.admin@medidoc.test",
    "name": "Anna Admin",
    "role": "admin"
  }
}
```

Der Benutzer kommt gleich mit, damit das Frontend nach dem Login keinen zweiten Request
braucht.

**Response `401`** — falsche E-Mail *oder* falsches Passwort, bewusst nicht unterscheidbar:

```json
{
  "status": 401,
  "message": "E-Mail oder Passwort ist falsch",
  "detail": "E-Mail oder Passwort ist falsch"
}
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
  "role": "admin"
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

## Die Form der Fehlerantworten

Seit dem 2026-08-04 haben **alle** Fehlerantworten der API dieselbe Form — auch die des
Logins:

```json
{ "status": 401, "message": "Anmeldung erforderlich" }
```

`message` ist deutsch und kann direkt angezeigt werden, `status` wiederholt den
HTTP-Status im Rumpf. Bei `422` kommt `errors` dazu, ein Eintrag je beanstandetem Feld.
Die vollständige Beschreibung steht in [patients-api.md](./patients-api.md#fehler), das
Format selbst in `backend/app/core/errors.py`.

`detail` bleibt zusätzlich erhalten, in genau der Form, die FastAPI ohne unser Zutun
erzeugt hätte — bestehender Frontend-Code bricht dadurch nicht. **Neuer Code liest
`message`.**

## Der Token

- Verfahren `HS256`, Secret aus `JWT_SECRET` in der `.env`
- Laufzeit **8 Stunden** (eine Praxis-Schicht), kein Refresh-Token
- Payload: `sub` (Benutzer-ID als String), `role`, `exp`

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

`AuthContext` hält `user` und `token`, schreibt den Token nach `localStorage` und liest ihn
beim Start wieder ein — mit einem `GET /auth/me`, um zu prüfen, ob er noch gilt.
`ProtectedRoute` leitet ohne gültigen Benutzer auf `/login` um.

### Die Rolle prüfen

`useAuth()` gibt dafür `hasRole` heraus. Damit hängt eine Aktion an der Rolle, ohne dass
eine Seite `user.role` selbst auseinandernimmt:

```jsx
const { hasRole } = useAuth();

{hasRole("admin") && <button onClick={loeschen}>Löschen</button>}
```

- Ohne angemeldeten Benutzer ist die Antwort `false` — kein Absturz an `user.role`.
- Mehrere Rollen werden als **Menge** geprüft: `hasRole("admin", "staff")` ist wahr, wenn
  der Benutzer eine davon hat — dieselbe Regel wie `require_roles` im Backend.

**Ausblenden ist Bedienkomfort, keine Absicherung — durchgesetzt wird im Backend.** Ein
ausgeblendeter Button ist kein Schutz: Wer den Request von Hand schickt, bekommt trotzdem
`403`. Deshalb bleibt die Prüfung im Backend die einzige, auf die es ankommt.

Kommt ein `403` zurück, steht in `error.message` der Satz **"Dazu fehlt dir die
Berechtigung"** — auch dann, wenn die Antwort selbst keine Meldung mitbringt
(`FORBIDDEN_ERROR` in `frontend/src/api.js`). Die Sitzung bleibt dabei bestehen, `apiFetch`
meldet nur bei `401` ab.

## Für das Backend

Zwei Dependencies stehen zur Verfügung, sobald der Login steht:

```python
# nur angemeldet
@router.get("/patients")
def list_patients(user: User = Depends(get_current_user)): ...

# angemeldet und in der erlaubten Rollenmenge
@router.delete("/patients/{patient_id}")
def delete_patient(
    patient_id: int,
    user: User = Depends(require_roles(Role.ADMIN)),
): ...
```

`require_roles` prüft gegen eine **Menge** erlaubter Rollen, nicht gegen eine Rangfolge —
Begründung in [ADR-0005](./adr/0005-rollen-admin-und-staff.md).

In Sprint 1 benutzt genau ein Endpunkt `require_roles`: das Löschen eines Patienten. Alle
anderen nehmen `get_current_user`.

## Benutzer-Modell

Tabelle `users` — `user` ist in Postgres ein reserviertes Wort.

| Feld | Typ | Hinweis |
| ---- | --- | ------- |
| `id` | int | Primärschlüssel |
| `email` | str | eindeutig, Login-Kennung |
| `name` | str | Anzeigename |
| `password_hash` | str | bcrypt, wird **nie** ausgeliefert |
| `role` | str | `admin` oder `staff` |
| `is_active` | bool | Standard `true`; inaktive Benutzer können sich nicht anmelden |
| `created_at` | datetime | |

Passwörter werden mit **bcrypt** gehasht (Paket `bcrypt` direkt, nicht `passlib` — passlib
1.7.4 ist unmaintained und bricht gegen bcrypt 4.x).

Nach außen geht nie das Model `User`, sondern immer `UserPublic` — dieselben Felder ohne
`password_hash`.

## Seed-Benutzer

Es gibt keine Selbstregistrierung. Benutzer entstehen über das Seed-Skript
(`python -m app.seed` aus `backend/`):

| E-Mail | Passwort | Rolle |
| ------ | -------- | ----- |
| `anna.admin@medidoc.test` | `geheim123` | `admin` |
| `tom.staff@medidoc.test` | `geheim123` | `staff` |

Reine Testdaten, wie das ganze Projekt. Für ein Deployment in Sprint 2 müssten sie ersetzt
werden.

## Abhängigkeiten

**Von Infra:** Die `.env` im Repo-Wurzelverzeichnis — dieselbe Datei, aus der Docker
Compose die `POSTGRES_*`-Variablen liest. Das Backend baut seine Verbindung aus denselben
Variablen zusammen und braucht zusätzlich `JWT_SECRET` und die `SEED_*`-Zugangsdaten.

**Zum Backend-Strang:** `engine` und `get_session` liegen in
`backend/app/db/session.py`, die Tabellenanlage in `backend/app/db/base.py`. Beides gehört
allen Strängen gemeinsam — wer eine Session braucht, nimmt `get_session` und legt keine
zweite Session-Verwaltung an. Der Aufbau des Backends steht in
[backend/README.md](../backend/README.md).

Der Login findet seinen Benutzer über `app.modules.users.service` (`get_by_email`,
`get_by_id`) und muss keine eigenen Queries schreiben. Passwörter prüft
`app.core.security.verify_password`.

## Nicht enthalten

Refresh-Token, Passwort-Reset, Selbstregistrierung, "Angemeldet bleiben",
Sperre nach zu vielen Fehlversuchen. Nichts davon ist für die Vorführung nötig.
