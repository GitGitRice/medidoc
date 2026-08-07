# Sprint 2 — Planungsvorschlag

> **Status:** Ergebnis des Sprint-2-Plannings. Entscheidungen unten sind getroffen, nicht
> mehr offen — Änderungen daran gehören ins Daily, nicht in einen Commit.

## Sprintziel

> Eine Praxis kann zu einem Patienten Dokumente mit Anhang führen (Dokumenttyp bestimmt die
> Felder, Anhang ist optional), ein Admin kann Benutzer anlegen, deaktivieren und ihre Rolle
> ändern, und die Anwendung läuft sowohl lokal über Docker Compose als auch auf AWS.

## Entschieden in diesem Planning

- **Dokument vs. Anhang folgt CONTEXT.md**, nicht dem, was PR #48 gebaut hat. Das dort
  entstandene Modell (Pflichtdatei, feste Felder für alle) ist ein **Anhang**, kein
  Dokument. Konsequenz: PR #48 wird nicht einfach gemerged, sondern überarbeitet — siehe
  Ticket 1/2 unten. ADR-0001 bleibt bestehen, keine Änderung an CONTEXT.md nötig.
- **Benutzerverwaltung ist Deaktivieren, nicht Löschen** — deckt sich mit ADR-0005
  ("anlegen, deaktivieren, Rolle ändern"). Ein Benutzer verschwindet nie hart aus der DB,
  schon weil der Audit-Trail auf Benutzer-IDs verweist.
- **AWS-Hosting ist ein verbindliches Sprint-2-Ziel**, keine Kür mehr. Docker Compose bleibt
  parallel der Weg für die lokale Entwicklung — AWS ersetzt Compose nicht, es kommt dazu.

## Arbeitspakete

| Strang | Zuständig | Issue | Inhalt Sprint 2 |
| ------ | --------- | ----- | --------------- |
| Backend Anhang | Tiran | #49 | PR #48 auf Anhang umbenennen, Datei optional, Download-Endpunkt, Pfadschema, Patient-Löschen-Reihenfolge |
| Backend Dokumenttyp | Tiran | #53 (blockiert durch #49) | Dokumenttyp mit typabhängigen Feldern |
| Frontend Anhang-Liste | Alexander | #56 (blockiert durch #53, #20) | Dokumente eines Patienten anzeigen |
| Frontend Anhang Suche | Alexander | #58 (blockiert durch #56) | Suchfeld über der Dokumentenliste |
| Frontend Anhang hochladen | Alexander | #57 (blockiert durch #53, #20) | Formular für Dokumenttyp + optionalen Anhang |
| Frontend Anhang löschen | Alexander | #59 (blockiert durch #56) | Löschen mit Rückfrage, nur `admin` |
| Backend Benutzerverwaltung | Steven | #50 | `POST`/Deaktivieren/Rolle ändern für Benutzer |
| Frontend Admin-Seite | Steven | #54 (blockiert durch #50) | Admin-Seite im Frontend |
| Infra | Dominik | #51 | AWS-Hosting, Docker Compose bleibt für lokal erhalten |
| Chore | Tiran | #52 | Mindestversion fastapi/starlette in `requirements.txt` |
| Frontend Fehlerseite | offen | #60 | Error Boundary für unerwartete Frontend-Fehler |

## Übernommen aus Sprint 1 (noch offen)

Diese existieren schon als Issues und brauchen kein neues Ticket, nur Fortsetzung:

| Issue/PR | Was fehlt |
| -------- | --------- |
| #18 / PR #43 | Code fertig, nur noch mergen |
| #19 | Suche in der Patientenübersicht — nicht begonnen |
| #20 | Patientendetailseite — noch ein Einzeiler-Stub, jetzt Voraussetzung für die Dokumenten-Ansicht |
| #21 | Patient anlegen/bearbeiten — nicht begonnen |
| #22 | Patient löschen mit Rückfrage — nicht begonnen |
| #34 | Code längst auf `develop` (PR #40), Issue hängt nur offen weil Gitflow-Merges nicht in den Default-Branch gehen — manuell schließen |
| PR #47 | Englische Doku-Vereinheitlichung, unabhängig mergebar |

## Abhängigkeiten

Die Reihenfolge, die die wenigsten Blockaden erzeugt:

1. **#49** (Anhang-Umbenennung, PR #48 überarbeiten) — blockiert #53 und #55.
2. **#53** (Dokumenttyp) — baut auf #49 auf.
3. **#20** (Patientendetailseite) fertigstellen — unabhängig von #49/#53, aber
   Voraussetzung für die Frontend-Anhang-Tickets.
4. **#56** (Anhang-Liste) und **#57** (Anhang hochladen) — beide blockiert durch #53, #20;
   **#58** (Suche) und **#59** (Löschen) bauen zusätzlich auf #56 auf, auf demselben Level
   wie #18–#22 bei den Patienten.
5. **#50 → #54** (Benutzerverwaltung, Backend vor Frontend) — unabhängig vom
   Dokumente-Strang, kann parallel laufen.
6. **#51** (AWS-Hosting) — unabhängig, kann parallel laufen; sinnvoll erst gegen Ende
   stabil zu halten, wenn die Feature-Arbeit nicht mehr jeden Tag das Compose-Setup ändert.
7. **#52** (Chore) — unabhängig, jederzeit möglich.
8. **#60** (Error Boundary) — unabhängig, betrifft die ganze Anwendung, noch niemandem
   zugewiesen.

PR #48 bleibt als Referenz offen (siehe Kommentar dort), wird aber nicht in dieser Form
gemerged — die Arbeit läuft über #49 weiter.

## Nicht im Scope

Unverändert gegenüber Sprint 1: Terminkalender, Abrechnung, e-Rezept/Medikationsplan,
Volltextsuche in Anhängen, Versionierung von Dokumenten.
