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

## Aufbau

Geschnitten nach **Feature**, nicht nach technischer Schicht. Alles zu einem Thema liegt
in einem Ordner unter `app/modules/`, damit zwei Leute an zwei Features arbeiten können,
ohne in dieselben Dateien zu fassen.

```
backend/
├── requirements.txt
├── testdata/
│   └── patients.json    200 erfundene Patienten
└── app/
    ├── main.py          App, CORS, /health — sonst nichts
    ├── seed.py          Einstiegspunkt Testdaten: ruft die Seeds der Module
    ├── api/router.py    hängt die Modul-Router ein — eine Zeile pro Modul
    ├── core/            fachlich neutral, gehört allen
    │   ├── config.py    Einstellungen aus der .env im Repo-Wurzelverzeichnis
    │   └── security.py  Passwort-Hashing (bcrypt)
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

- **Die Patienten-Endpunkte sind noch ungeschützt.** So im
  [Sprint-1-Plan](../docs/sprint-1-plan.md) vorgesehen, damit Frontend und Backend nicht
  auf den Login warten. Sobald `modules/auth/dependencies.py` steht, kommt an jeden
  Endpunkt ein `Depends(get_current_user)` und an `DELETE` ein
  `Depends(require_roles(Role.ADMIN))` — die einzige Stelle im Sprint 1, die eine Rolle
  prüft ([ADR-0005](../docs/adr/0005-rollen-admin-und-staff.md)). Die genauen Zeilen
  stehen oben in [modules/patients/router.py](app/modules/patients/router.py). Die Stubs
  werfen bis dahin `NotImplementedError` und winken bewusst niemanden durch.
- **`/patients` oder `/patienten`?** CONTEXT.md und ADR-0005 legen fest, dass die API
  durchgehend englisch ist; die Beispiele in docs/auth-api.md schrieben dagegen
  `/patienten` und sind auf `/patients` gezogen worden. ADR-0005 nennt als angenommene
  Entscheidung weiterhin `/patienten` und wird nicht nachträglich geändert —
  **einmal im Daily bestätigen.**
- **Keine Migrationen.** `create_all` legt nur fehlende Tabellen an. Für Sprint 1
  bewusst so, siehe oben.

Die fachlichen offenen Punkte zur Patienten-API (keine E-Mail-Prüfung, kein
Sortierparameter) stehen in [docs/patients-api.md](../docs/patients-api.md#offene-punkte).
