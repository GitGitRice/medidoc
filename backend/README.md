# Backend

FastAPI + SQLModel gegen PostgreSQL.

| | |
| - | - |
| Fachliche Begriffe | [CONTEXT.md](../CONTEXT.md) |
| Patienten-API | [docs/patients-api.md](../docs/patients-api.md) |
| Auth-API | [docs/auth-api.md](../docs/auth-api.md) |
| Entscheidungen | [docs/adr/](../docs/adr/) |

> **Sprache:** Code und API sind englisch, deutsch ist nur die Oberfläche im Frontend.
> Kommentare und Doku sind deutsch, Bezeichner und JSON-Keys englisch.

## Lokal starten

Aus dem Repo-Wurzelverzeichnis. Einmalig `.env` anlegen:

```bash
cp .env.example .env
```

Dann alles hochfahren:

```bash
docker compose up
```

API auf <http://localhost:8000>, interaktive Doku auf <http://localhost:8000/docs>.

Testdaten anlegen — 2 Benutzer und 200 Patienten, mehrfach ausführbar, Vorhandenes wird
übersprungen:

```bash
docker compose exec fastapi python -m app.seed
```

Weniger Patienten, wenn es nur ums Ausprobieren geht:

```bash
docker compose exec fastapi python -m app.seed --patients 50
```

Bei Modelländerungen zieht `create_all` geänderte Spalten **nicht** nach. Tabellen
wegwerfen und neu seeden:

```bash
docker compose down -v && docker compose up -d && docker compose exec fastapi python -m app.seed
```

## Tests

```bash
docker compose exec fastapi pytest
```

Oder ohne Docker, aus `backend/` und mit installierten Abhängigkeiten: `pytest`.

Die Tests laufen gegen **SQLite im Speicher**, nicht gegen Postgres — sie brauchen keine
laufende Datenbank und hinterlassen keine Daten. Die Session wird der App über
`app.dependency_overrides[get_session]` untergeschoben, die echte Engine bleibt
unangetastet. Fixtures stehen in [tests/conftest.py](tests/conftest.py); `make_user` legt
einen Benutzer mit Klartext-Passwort an.

Eine `.env` im Repo-Wurzelverzeichnis muss vorhanden sein: `app.core.config` liest sie
beim Import, auch im Test.

## Aufbau

Geschnitten nach **Feature**, nicht nach technischer Schicht. Alles zu einem Thema liegt
in einem Ordner unter `app/modules/`, damit zwei Leute an zwei Features arbeiten können,
ohne in dieselben Dateien zu fassen.

```
backend/
├── requirements.txt
├── pytest.ini
├── tests/               laufen gegen SQLite im Speicher, ohne Docker
├── testdata/
│   └── patients.json    200 erfundene Patienten
└── app/
    ├── main.py          App, CORS, /health — sonst nichts
    ├── seed.py          Einstiegspunkt Testdaten: ruft die Seeds der Module
    ├── api/router.py    hängt die Modul-Router ein — eine Zeile pro Modul
    ├── core/            fachlich neutral, gehört allen
    │   ├── config.py    Einstellungen aus der .env im Repo-Wurzelverzeichnis
    │   └── security.py  Passwort-Hashing (bcrypt) und Token ausstellen (JWT)
    ├── db/              fachlich neutral, gehört allen
    │   ├── session.py   engine, get_session
    │   └── base.py      kennt alle Models, legt Tabellen an
    └── modules/
        ├── patients/    Strang B — Tiran
        ├── users/       Benutzer-Model, Verwaltung ist Sprint 2
        └── auth/        Strang C — Steven
```

Jedes Modul hat, was es braucht, immer unter demselben Namen:

| Datei | Inhalt | Darf FastAPI kennen |
| ----- | ------ | ------------------- |
| `models.py` | SQLModel-Tabelle | nein |
| `schemas.py` | Ein- und Ausgabeformen der API | nein |
| `service.py` | Logik und Datenbankzugriffe | **nein** |
| `router.py` | Endpunkte | ja |
| `seed.py` | Testdaten des Moduls | nein |

Die eine Regel, die den Rest trägt: **`service.py` kennt kein HTTP.** Keine
`HTTPException`, keine Statuscodes, keine `Depends`. Der Router übersetzt zwischen beidem.
Dadurch bleibt die Logik einzeln testbar und der Router kurz genug, um ihn am Stück zu
lesen.

### Wer fasst was an

Die Aufteilung ist so gewählt, dass Merge-Konflikte selten sind:

| Bereich | Strang |
| ------- | ------ |
| `modules/patients/` | Tiran |
| `modules/auth/`, `modules/users/` | Steven |
| `docker-compose.yml`, `.env.example` | Dominik |
| `core/`, `db/`, `api/router.py`, `main.py` | gemeinsam — Änderungen bitte ins Daily |

### Ein neues Modul dazunehmen

1. Ordner unter `app/modules/` anlegen, mit `__init__.py`.
2. `router.py` mit eigenem `prefix` und `tags`.
3. Eine Import-Zeile in [app/api/router.py](app/api/router.py).
4. Hat das Modul Tabellen: eine Import-Zeile in [app/db/base.py](app/db/base.py) —
   sonst fehlt die Tabelle beim Anlegen, **ohne dass irgendwo ein Fehler auftaucht**.
5. Hat es Testdaten: `seed.py` und eine Zeile in [app/seed.py](app/seed.py).

## Auth-API

Der vollständige Vertrag steht in **[docs/auth-api.md](../docs/auth-api.md)**. Hier nur,
was schon steht:

| Methode | Pfad | Zweck | Stand |
| ------- | ---- | ----- | ----- |
| `POST` | `/auth/login` | E-Mail und Passwort gegen ein JWT tauschen | fertig |
| `GET` | `/auth/me` | Benutzer zum Token | fertig |

Der Login ist **formular-kodiert**, nicht JSON (`OAuth2PasswordRequestForm`) — nur so
funktioniert der *Authorize*-Button in `/docs`. Das Feld heißt `username` und enthält die
E-Mail.

Zwei Dinge, die beim Lesen sonst überraschen:

- **`authenticate` gibt bei drei verschiedenen Fehlern dasselbe `None` zurück** —
  E-Mail unbekannt, Passwort falsch, Benutzer deaktiviert. Der Router kann sie damit
  nicht unterscheiden, und das `401` verrät nichts. Aus demselben Grund läuft bei einer
  unbekannten E-Mail trotzdem eine bcrypt-Prüfung gegen einen Dummy-Hash.
- **E-Mails werden normalisiert gespeichert und normalisiert gesucht**
  (`users.service.normalize_email`). Ohne diese Regel würden `Anna.Admin@…` und
  `anna.admin@…` zwei Konten.

## Patienten-API

Der vollständige Vertrag steht in **[docs/patients-api.md](../docs/patients-api.md)** —
Felder, Beispielantworten, Fehlerfälle, Hinweise fürs Frontend. Hier nur der Überblick:

| Methode | Pfad | Zweck |
| ------- | ---- | ----- |
| `GET` | `/patients?q=&limit=&offset=` | Patientenübersicht, durchsuchbar und seitenweise |
| `POST` | `/patients` | anlegen → `201` |
| `GET` | `/patients/{id}` | Stammdaten |
| `PATCH` | `/patients/{id}` | einzelne Felder ändern |
| `DELETE` | `/patients/{id}` | endgültig löschen → `204` |

Zwei Dinge, die beim Lesen des Codes sonst überraschen:

- **Nur drei Pflichtfelder** — `first_name`, `last_name`, `date_of_birth`. Ein Patient
  ohne Telefonnummer und ohne Versicherung ist gültig.
- `GET /patients` liefert `{ items, total, limit, offset }`, keine nackte Liste. `total`
  ist die Trefferzahl ohne Paging.

Damit die Doku nicht doppelt gepflegt werden muss: Alles Fachliche gehört nach
`docs/patients-api.md`, hier steht nur, wie der Code aufgebaut ist.

## Testdaten

[`testdata/patients.json`](testdata/patients.json) — 200 frei erfundene Patienten, in
derselben Form wie der Rumpf von `POST /patients`. **Das Frontend kann die Datei direkt
als Mock benutzen**, solange es noch nicht gegen die API baut.

Als JSON neben dem Code und nicht als Python-Literal darin: So kommt das Frontend an
dieselben Daten, und neue Fälle kommen dazu, ohne dass jemand Python anfasst. JSON statt
YAML, weil `json` in der Standardbibliothek liegt — YAML wäre eine Abhängigkeit für nichts.

Die ersten sieben Datensätze sind von Hand geschrieben; auf sie beziehen sich die
Beispiele in der Doku. Der Rest ist erzeugt und deckt bewusst die unbequemen Fälle ab:
Umlaute und türkische Zeichen in Namen, Familien unter derselben Adresse, Patienten ohne
Adresse, ohne E-Mail oder ohne Versicherung, Geburtsdaten von 1930 bis 2025.

Beim Seed läuft **jeder Datensatz durch dieselbe Prüfung wie ein echter `POST`**. Ein
kaputter Eintrag fällt damit sofort auf und nicht erst, wenn das Frontend ihn anzeigt.

## Offene Punkte

- **`/patients` oder `/patienten`?** CONTEXT.md und ADR-0005 legen fest, dass die API
  durchgehend englisch ist; die Beispiele in docs/auth-api.md schrieben dagegen
  `/patienten` und sind auf `/patients` gezogen worden. ADR-0005 nennt als angenommene
  Entscheidung weiterhin `/patienten` und wird nicht nachträglich geändert —
  **einmal im Daily bestätigen.**
- **Keine Migrationen.** `create_all` legt nur fehlende Tabellen an. Für Sprint 1
  bewusst so, siehe oben.

Die fachlichen offenen Punkte zur Patienten-API (keine E-Mail-Prüfung, kein
Sortierparameter) stehen in [docs/patients-api.md](../docs/patients-api.md#offene-punkte).
