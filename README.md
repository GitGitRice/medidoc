# MediDoc

Eine digitale Patientenakte für Arztpraxen — Abschlussprojekt Modul 3, Syntax IT-Kurs.

Die Praxis verwaltet ihre Patienten und die zu ihnen gehörenden Dokumente an einem Ort:
Patientenübersicht als durchsuchbare Tabelle, Stammdatenpflege und eine Akte pro Patient,
in der Befunde, Arztbriefe und Laborwerte abgelegt werden.

> **Status:** Sprint 1. Anmeldung und die Patienten-Endpunkte stehen, im Frontend stehen
> Login, geschütztes Routing und die Patientenübersicht (Tabelle, Paginierung,
> Navigation zur Detailseite) — die Detailseite selbst ist noch ein Platzhalter.
> Fachliche Begriffe in [CONTEXT.md](./CONTEXT.md),
> Entscheidungen in [docs/adr/](./docs/adr/), Sprint-1-Plan in
> [docs/sprint-1-plan.md](./docs/sprint-1-plan.md).

## Team

| Name | Strang |
| ---- | ------ |
| Steven Tanu | Auth |
| Dominik | Infra & DevOps |
| Tiran | Backend & Daten |
| Farhad | Frontend |

## Tech-Stack

- **Frontend:** React (Vite), React Router, Context API, Material UI
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
Pull Request — und bei Bedarf von Hand.

```bash
cd backend  && pytest -q
cd frontend && npm test
```

### CI neu anstoßen

Manchmal fehlen die Checks an einem Pull Request komplett. Der häufigste Grund: Ein
Force-Push lässt den Pull Request auf einem Commit stehen, für den nie ein Lauf
angelegt wurde. Dann gibt es auch nichts zum Neustarten — der Lauf muss neu erzeugt
werden.

| Situation | Befehl |
| --------- | ------ |
| Ein Lauf existiert, soll noch mal laufen | `gh run rerun <id>` — nur die roten Jobs mit `--failed` |
| Für den Commit existiert kein Lauf | `gh workflow run ci.yml --ref <branch>` |
| Geht immer, ohne Voraussetzung | `gh pr close <nr> && gh pr reopen <nr>` |

Die Lauf-ID findet man über `gh run list --branch <branch>`.

Zwei Fallstricke bei `gh workflow run`: Ob der Workflow von Hand startbar ist, prüft
GitHub am Standard-Branch — ausgeführt wird aber die `ci.yml` **des angegebenen
Branches**. Ein Branch, der vor dieser Änderung abgezweigt wurde, kennt
`workflow_dispatch` noch nicht; dort vorher `develop` hereinmergen. Und ob der Lauf am
Pull Request als Check auftaucht, sollte man beim ersten Mal wirklich nachsehen: Er
läuft auf dem Head-Commit des Branches und sollte deshalb dort landen — bestätigt ist
das noch nicht.

Close und Reopen ist deshalb der verlässliche Weg, wenn es nur darum geht, die Checks
an einem Pull Request nachzuholen.

## Scope

**Im Scope:** Authentifizierung, Patientenverwaltung (anlegen, suchen, bearbeiten,
löschen), Akte pro Patient, Dokumente mit typabhängigen Feldern und optionalem Anhang.

**Nicht im Scope:** Terminkalender, Abrechnung, e-Rezept, Volltextsuche in Anhängen,
Versionierung, Anbindung echter Praxissoftware. Begründungen im
[Sprint-1-Plan](./docs/sprint-1-plan.md#nicht-im-scope).

## Lokal starten

Falls noch keine `.env` existiert, einmalig die Beispielkonfiguration kopieren und
anschließend den vollständigen Stack starten:

```bash
cp .env.example .env
docker compose up --build
```

Danach sind das Frontend unter <http://localhost:5173>, die API unter
<http://localhost:8000> und deren interaktive Dokumentation unter
<http://localhost:8000/docs> erreichbar. Änderungen an Frontend und Backend werden
von den Entwicklungsservern automatisch übernommen.

PostgreSQL speichert die Patientenstammdaten im Volume `postgres_data`. MongoDB legt
Dokument-Metadaten im Volume `mongo_data` ab; die eigentlichen Anhänge liegen getrennt
im Volume `uploads_data`. `docker compose down` behält diese Daten, während
`docker compose down -v` alle drei Volumes und deren Inhalte löscht.

### Testdaten anlegen

Frisch hochgefahren ist die Datenbank leer — es gibt noch keinen Benutzer, mit dem man
sich anmelden könnte. Ein Aufruf legt alles auf einmal an: die beiden Startbenutzer,
200 Testpatienten und 17 Dokumente in den Akten der ersten sechs.

```bash
docker compose exec fastapi python -m app.seed
```

Der Seed ist mehrfach ausführbar — Vorhandenes wird übersprungen, nicht überschrieben.

**Benutzer.** Es gibt keine Selbstregistrierung; Benutzer entstehen in Sprint 1 nur über
den Seed. Zugangsdaten und Rollen stehen in der `.env` (`SEED_ADMIN_*`, `SEED_STAFF_*`),
die Voreinstellung aus `.env.example`:

| E-Mail | Passwort | Rolle |
| ------ | -------- | ----- |
| `anna.admin@medidoc.test` | `geheim123` | `admin` |
| `tom.staff@medidoc.test` | `geheim123` | `staff` |

Wer andere Zugangsdaten will, ändert sie in der `.env` **vor** dem ersten Seed — ein
zweiter Lauf erkennt den bestehenden Benutzer an seiner E-Mail und ändert kein Passwort.
Details in [docs/auth-api.md](./docs/auth-api.md#seed-benutzer).

**Patienten und Dokumente.** Beide kommen aus `backend/testdata/` und laufen dabei durch
dieselbe Prüfung wie ein echter `POST`. Für schnelleres Ausprobieren reicht ein Teil:

```bash
docker compose exec fastapi python -m app.seed --patients 50   # nur die ersten 50
docker compose exec fastapi python -m app.seed --no-documents  # ohne MongoDB
```

Die Dokumente brauchen MongoDB (ADR-0002); fehlt `MONGO_URL`, werden sie übersprungen und
der Rest läuft trotzdem durch. Ihre Anhänge sind Platzhalter: Name, Typ und Größe stimmen,
die Bytes sind ein kurzer Text — ausgeliefert werden sie ohnehin nicht, einen
Download-Endpunkt gibt es noch nicht.

Bei Modelländerungen zieht `create_all` geänderte Spalten **nicht** nach. Dann hilft nur
wegwerfen und neu seeden:

```bash
docker compose down -v && docker compose up -d && docker compose exec fastapi python -m app.seed
```

## AWS-Demo

Zusätzlich zum lokalen Compose-Stack läuft MediDoc für die Projektvorführung auf AWS
EC2. Architektur, Einrichtung und Betrieb stehen in der
[AWS-Deployment-Dokumentation](./docs/aws-deployment.md).
### Testdaten anlegen

Frisch hochgefahren ist die Datenbank leer — es gibt noch keinen Benutzer, mit dem man
sich anmelden könnte. Ein Aufruf legt alles auf einmal an: die beiden Startbenutzer,
200 Testpatienten und 17 Dokumente in den Akten der ersten sechs.

```bash
docker compose exec fastapi python -m app.seed
```

Der Seed ist mehrfach ausführbar — Vorhandenes wird übersprungen, nicht überschrieben.

**Benutzer.** Es gibt keine Selbstregistrierung; Benutzer entstehen in Sprint 1 nur über
den Seed. Zugangsdaten und Rollen stehen in der `.env` (`SEED_ADMIN_*`, `SEED_STAFF_*`),
die Voreinstellung aus `.env.example`:

| E-Mail | Passwort | Rolle |
| ------ | -------- | ----- |
| `anna.admin@medidoc.test` | `geheim123` | `admin` |
| `tom.staff@medidoc.test` | `geheim123` | `staff` |

Wer andere Zugangsdaten will, ändert sie in der `.env` **vor** dem ersten Seed — ein
zweiter Lauf erkennt den bestehenden Benutzer an seiner E-Mail und ändert kein Passwort.
Details in [docs/auth-api.md](./docs/auth-api.md#seed-benutzer).

**Patienten und Dokumente.** Beide kommen aus `backend/testdata/` und laufen dabei durch
dieselbe Prüfung wie ein echter `POST`. Für schnelleres Ausprobieren reicht ein Teil:

```bash
docker compose exec fastapi python -m app.seed --patients 50   # nur die ersten 50
docker compose exec fastapi python -m app.seed --no-documents  # ohne MongoDB
```

Die Dokumente brauchen MongoDB (ADR-0002); fehlt `MONGO_URL`, werden sie übersprungen und
der Rest läuft trotzdem durch. Ihre Anhänge sind Platzhalter: Name, Typ und Größe stimmen,
die Bytes sind ein kurzer Text — ausgeliefert werden sie ohnehin nicht, einen
Download-Endpunkt gibt es noch nicht.

Bei Modelländerungen zieht `create_all` geänderte Spalten **nicht** nach. Dann hilft nur
wegwerfen und neu seeden:

```bash
docker compose down -v && docker compose up -d && docker compose exec fastapi python -m app.seed
```

## Projektstruktur

```
backend/            FastAPI-API, nach Features geschnitten — siehe backend/README.md
backend/tests/      pytest gegen SQLite im Speicher, braucht kein Docker
backend/testdata/   erfundene Testdaten als JSON: 200 Patienten, 17 Dokumente
frontend/           React (Vite)
deploy/             Bootstrap- und Betriebsskripte für AWS
docs/               ADRs, Sprint-Plan, API-Verträge
```

Aufbau und Zuständigkeiten stehen in [backend/README.md](./backend/README.md).

## API-Verträge

Damit Frontend und Backend parallel arbeiten können, steht die Form der Endpunkte fest,
bevor sie fertig sind:

- [docs/patients-api.md](./docs/patients-api.md) — Patientenübersicht, Stammdaten, CRUD
- [docs/auth-api.md](./docs/auth-api.md) — Login, Token, Rollen
- [docs/documents-api.md](./docs/documents-api.md) — Dokumente je Patient: anlegen, auflisten, löschen
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

Das Tagebuch steht in **[docs/Diary.md](./docs/Diary.md)** — ein Eintrag pro Person und
Tag, neueste oben. Jeder ergänzt seinen eigenen vor Feierabend.

Bewusst nur an einer Stelle: Zwei Tagebücher heißen, dass beide veralten.

### Sprint Review und Retrospektive

| Woche | Review | Retrospektive |
| ----- | ------ | ------------- |
| 1 | _tbd_ | _tbd_ |
| 2 | _tbd_ | _tbd_ |

## Entscheidungen

Architektur- und Technologieentscheidungen werden als ADRs in `docs/adr/` festgehalten.

## Hinweis zu Daten

Reines Übungsprojekt. Es werden ausschließlich frei erfundene Testdaten verwendet —
keine echten Patientendaten.
