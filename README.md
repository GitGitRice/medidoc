# MediDoc

Eine digitale Patientenakte für Arztpraxen — Abschlussprojekt Modul 3, Syntax IT-Kurs.

Die Praxis verwaltet ihre Patienten und die zu ihnen gehörenden Dokumente an einem Ort:
Patientenübersicht als durchsuchbare Tabelle, Stammdatenpflege und eine Akte pro Patient,
in der Befunde, Arztbriefe und Laborwerte abgelegt werden.

> **Status:** Konzeptphase. Fachliche Begriffe in [CONTEXT.md](./CONTEXT.md),
> Entscheidungen in [docs/adr/](./docs/adr/), Planungsvorschlag für Sprint 1 in
> [docs/sprint-1-plan.md](./docs/sprint-1-plan.md).

## Team

| Name | Strang |
| ---- | ------ |
| Steven Tanu | Auth |
| Dominik | Infra & DevOps |
| Tiran | Backend & Daten |
| Farhad | Frontend |

## Tech-Stack

- **Frontend:** React (Vite), React Router, Context API
- **Backend:** FastAPI (Python)
- **Datenbanken:** PostgreSQL für Patientenstammdaten, MongoDB für Dokumente
  — Begründung in [ADR-0002](./docs/adr/0002-postgres-fuer-stammdaten-mongodb-fuer-dokumente.md)
- **Infrastruktur:** Docker Compose

## Arbeitsweise

Wir arbeiten nach **Gitflow** — Begründung und Details in
[ADR-0006](./docs/adr/0006-gitflow-als-branching-modell.md).

| Branch | Bedeutung |
| ------ | --------- |
| `main` | Der vorführbare Stand. Nur Merges aus `develop`. |
| `develop` | Integration aller Stränge. Nur Merges aus `feature/*`. |
| `feature/<issue>-<kurzname>` | Ein Issue, ein Branch — z. B. `feature/14-auth-login` |

Ein Issue = ein Branch = ein Pull Request nach `develop`, den ein anderes Teammitglied
anschaut. Kein direkter Push auf `main` oder `develop`. `release/*` und `hotfix/*`
benutzen wir bewusst nicht.

**Ausnahme `feature/auth`:** Die Authentifizierung (Issues #13–#17) hängt so eng
zusammen, dass die einzelnen Branches aufeinander aufbauen statt nebeneinander zu
laufen. Sie gehen deshalb als Pull Request nach `feature/auth`; dieser Branch geht
am Ende als ein Pull Request nach `develop`. Ein Pull Request gegen `feature/auth`
ist also kein falsches Ziel. Für alles außerhalb der Auth-Strecke bleibt es bei
`develop` als Ziel.

## Tests

Backend und Frontend haben je eine eigene Suite. Beide laufen ohne Docker und ohne
Datenbank — das Backend gegen SQLite im Speicher, das Frontend gegen jsdom.
[GitHub Actions](./.github/workflows/ci.yml) startet sie bei jedem Push und jedem
Pull Request.

```bash
cd backend  && pytest -q
cd frontend && npm test
```

## Scope

**Im Scope:** Authentifizierung, Patientenverwaltung (anlegen, suchen, bearbeiten,
löschen), Akte pro Patient, Dokumente mit typabhängigen Feldern und optionalem Anhang.

**Nicht im Scope:** Terminkalender, Abrechnung, e-Rezept, Volltextsuche in Anhängen,
Versionierung, Anbindung echter Praxissoftware. Begründungen im
[Sprint-1-Plan](./docs/sprint-1-plan.md#nicht-im-scope).

## Lokal starten

Falls noch keine `.env` existiert, einmalig die Beispielkonfiguration kopieren und
anschließend die Services starten:

```bash
cp .env.example .env
docker compose up --build
```

Die API ist danach unter <http://localhost:8000> und ihre interaktive Dokumentation
unter <http://localhost:8000/docs> erreichbar.

PostgreSQL speichert die Patientenstammdaten im Volume `postgres_data`. MongoDB legt
Dokument-Metadaten im Volume `mongo_data` ab; die eigentlichen Anhänge liegen getrennt
im Volume `document_attachments`. `docker compose down` behält diese Daten, während
`docker compose down -v` alle drei Volumes und deren Inhalte löscht.

## Projektstruktur

```
backend/            FastAPI-API, nach Features geschnitten — siehe backend/README.md
backend/tests/      pytest gegen SQLite im Speicher, braucht kein Docker
backend/testdata/   200 erfundene Testpatienten als JSON, auch als Frontend-Mock nutzbar
frontend/           React (Vite)
docs/               ADRs, Sprint-Plan, API-Verträge
```

Aufbau und Zuständigkeiten stehen in [backend/README.md](./backend/README.md).

## API-Verträge

Damit Frontend und Backend parallel arbeiten können, steht die Form der Endpunkte fest,
bevor sie fertig sind:

- [docs/patients-api.md](./docs/patients-api.md) — Patientenübersicht, Stammdaten, CRUD
- [docs/auth-api.md](./docs/auth-api.md) — Login, Token, Rollen
- [docs/logging-monitoring.md](./docs/logging-monitoring.md) — Log, Audit-Trail, Missbrauchserkennung

## Sprints

Zwei Sprints à eine Woche, Präsentation in Woche 3.

### Sprint 1 — _Woche 1_

**Sprintziel (Vorschlag, wird Montag beschlossen):** Ein Benutzer kann sich anmelden,
sieht die Patientenübersicht als durchsuchbare Tabelle, kann einen Patienten öffnen und
dessen Stammdaten sehen, und kann Patienten anlegen, bearbeiten und löschen. Läuft lokal
über Docker Compose gegen PostgreSQL.

Aufgabenverteilung siehe [Sprint-1-Plan](./docs/sprint-1-plan.md) und GitHub Issues.

### Sprint 2 — _Woche 2_

**Sprintziel (Entwurf):** Dokumente in der Akte — anlegen mit typabhängigen Feldern,
Anhang hochladen und wieder herunterladen, Dokumentenliste pro Patient. MongoDB kommt
dazu.

### Woche 3

Test, Dokumentation, Abschlusspräsentation.

## Projekttagebuch

Tägliche Einträge: Was wurde erledigt, woran wird gearbeitet, welche Hindernisse gibt es.

### Woche 1

| Tag | Ergebnisse | Hindernisse |
| --- | ---------- | ----------- |
| Mo | | |
| Di | | |
| Mi | | |
| Do | | |
| Fr | | |

**Sprint Review:** _tbd_
**Retrospektive:** Was lief gut / Was hat gebremst / Was verbessern wir

### Woche 2

| Tag | Ergebnisse | Hindernisse |
| --- | ---------- | ----------- |
| Mo | | |
| Di | | |
| Mi | | |
| Do | | |
| Fr | | |

**Sprint Review:** _tbd_
**Retrospektive:** _tbd_

## Entscheidungen

Architektur- und Technologieentscheidungen werden als ADRs in `docs/adr/` festgehalten.

## Hinweis zu Daten

Reines Übungsprojekt. Es werden ausschließlich frei erfundene Testdaten verwendet —
keine echten Patientendaten.
