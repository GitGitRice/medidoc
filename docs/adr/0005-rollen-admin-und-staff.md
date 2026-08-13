---
status: accepted
supersedes: 0004
---

# Zwei Rollen: `admin` und `staff`

ADR-0004 hatte für Sprint 1 bewusst nur eine Rolle vorgesehen, um die Testfläche klein zu
halten. Wir führen stattdessen von Anfang an zwei Rollen ein — `admin` und `staff` —, weil
das Rollenfeld selbst fast nichts kostet, das nachträgliche Einziehen aber teuer ist: eine
Migration plus eine Anpassung an jeder bereits geschützten Route. Der eigentliche Einwand
aus ADR-0004 bleibt trotzdem gültig und wird anders adressiert: Nicht die Anzahl der Rollen
verdoppelt die Testfläche, sondern die Anzahl der Stellen, an denen geprüft wird. Sprint 1
prüft an genau **einer** Stelle.

> **Sprache:** Code und API sind durchgehend englisch, deutsch ist nur die Oberfläche im
> Frontend. Die Rolle heißt im Code und im JSON also `staff`, in dieser Begründung aus
> Lesbarkeitsgründen weiterhin "Mitarbeiter".

## Rechte statt Berufe

Rollen können zwei verschiedene Dinge abbilden: was jemand im Beruf ist (Arzt, MFA) oder
was jemand in der Anwendung darf (Verwaltung ja/nein). Wir modellieren die **Rechte-Achse**.
Grund: In unserem Scope unterscheidet sich keine Funktion nach Beruf — nirgends steht, dass
nur ein Arzt einen Befund anlegen darf. Eine Berufs-Achse wäre also eine Unterscheidung
ohne Konsequenz.

## Wer darf was

| Rolle | Darf |
| ----- | ---- |
| `staff` | Patienten lesen, anlegen, bearbeiten; Dokumente lesen und anlegen |
| `admin` | alles von `staff`, zusätzlich Patienten löschen und Benutzer verwalten |

In Sprint 1 ist davon genau eine Zeile wirksam: **`DELETE /patients/{id}` verlangt
`admin`**, alles andere verlangt nur einen gültigen Token. Die Benutzerverwaltung
(anlegen, deaktivieren, Rolle ändern) ist Sprint 2. Damit gibt es einen sichtbaren,
vorführbaren Rollenunterschied und keine Rollenlogik, die über die Anwendung verstreut ist.

Löschen ist bewusst der Unterschied: Es ist die einzige Aktion, die Daten unwiederbringlich
entfernt, und in einer echten Praxis auch die einzige, bei der eine Rückfrage üblich wäre.

## Erweiterbarkeit: `staff` kann später aufgeteilt werden

`staff` kann später in `doctor` und `assistant` zerfallen. Wichtig für den Entwurf: Diese
beiden wären **gleichrangig**, nicht gestuft — die MFA pflegt Stammdaten, der Arzt schreibt
Befunde, keiner ist eine Obermenge des anderen. Eine Prüfung nach dem Muster "Rolle
mindestens X" würde dabei brechen.

Deshalb wird von Anfang an mengenbasiert geprüft: eine Dependency
`require_roles(*allowed_roles)`, die die Rolle des Benutzers gegen eine Menge erlaubter
Rollen hält. Bei zwei Rollen sieht das aus wie eine Hierarchie, bei vier Rollen trägt es
trotzdem noch. Der Aufruf lautet also `require_roles(Role.ADMIN)` und nicht
`require_min_role(Role.ADMIN)`.

## Speicherung

Die Rolle liegt als **String-Spalte** in PostgreSQL, nicht als PostgreSQL-`ENUM`-Typ.
Gültige Werte kommen aus einem Python-Enum und werden in der API validiert. Grund: Solange
die Rollenliste noch wachsen kann, ist ein `ALTER TYPE` pro neuer Rolle unnötiger Aufwand;
die Datenbank gewinnt hier nichts, was die API nicht ohnehin prüft.

## Konsequenzen

- ADR-0004 ist damit abgelöst.
- Das Seed-Skript muss mindestens einen `admin` anlegen, sonst ist die Benutzerverwaltung
  in Sprint 2 von niemandem erreichbar.
- Es gibt keine Selbstregistrierung. Benutzer entstehen in Sprint 1 ausschließlich über
  den Seed.
- Das Ausblenden von Buttons im Frontend anhand der Rolle ist Bedienkomfort, keine
  Absicherung. Durchgesetzt wird ausschließlich im Backend.
- Wenn `staff` später aufgeteilt wird, gilt der Hinweis aus ADR-0004 unverändert: erst die
  Tabelle "wer darf was" gemeinsam festlegen und abnehmen, dann implementieren.
