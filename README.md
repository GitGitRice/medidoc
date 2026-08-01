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
| _tbd_ | Infra & DevOps |
| _tbd_ | Backend & Daten |
| _tbd_ | Frontend |

## Tech-Stack

- **Frontend:** React (Vite), React Router, Context API
- **Backend:** FastAPI (Python)
- **Datenbanken:** PostgreSQL für Patientenstammdaten, MongoDB für Dokumente
  — Begründung in [ADR-0002](./docs/adr/0002-postgres-fuer-stammdaten-mongodb-fuer-dokumente.md)
- **Infrastruktur:** Docker Compose

## Scope

**Im Scope:** Authentifizierung, Patientenverwaltung (anlegen, suchen, bearbeiten,
löschen), Akte pro Patient, Dokumente mit typabhängigen Feldern und optionalem Anhang.

**Nicht im Scope:** Terminkalender, Abrechnung, e-Rezept, Volltextsuche in Anhängen,
Versionierung, Anbindung echter Praxissoftware. Begründungen im
[Sprint-1-Plan](./docs/sprint-1-plan.md#nicht-im-scope).

## Lokal starten

_Folgt, sobald das Setup steht._

## Projektstruktur

_Folgt._

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
