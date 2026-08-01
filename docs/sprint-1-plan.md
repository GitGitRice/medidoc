# Sprint 1 — Planungsvorschlag

> **Status:** Vorschlag als Diskussionsgrundlage für das Sprint Planning am Montag,
> 09:00–10:00 Uhr. Nichts hier ist beschlossen — die offenen Punkte am Ende sind bewusst
> offen gelassen.

## Sprintziel

> Ein Benutzer kann sich anmelden, sieht die Patientenübersicht als durchsuchbare Tabelle,
> kann einen Patienten öffnen und dessen Stammdaten sehen, und kann Patienten anlegen,
> bearbeiten und löschen. Läuft lokal über Docker Compose gegen PostgreSQL.

Bewusst **ohne** Dokumente und ohne MongoDB — das ist Sprint 2. Damit ist am Freitag der
ersten Woche eine vollständige, vorführbare Anwendung fertig, auch wenn Sprint 2 nicht
komplett aufgeht.

## Arbeitspakete

Die Aufteilung ist so gewählt, dass sich die vier Stränge möglichst wenig gegenseitig
blockieren.

| # | Strang | Zuständig | Inhalt Sprint 1 | Inhalt Sprint 2 |
| - | ------ | --------- | --------------- | --------------- |
| **A** | Infra & DevOps | _tbd_ | Docker Compose, PostgreSQL-Service, `.env`, Setup-Doku | MongoDB-Service, Volume für Anhänge, ggf. Deployment |
| **B** | Backend & Daten | _tbd_ | SQLModel `Patient`, Seed-Daten, CRUD-Endpunkte | Dokument-Endpunkte gegen MongoDB, Datei-Upload |
| **C** | Auth | Steven | User-Model, Login-Endpunkt, Token, `AuthContext` | ggf. Rollen (siehe ADR-0004) |
| **D** | Frontend | _tbd_ | Patientenübersicht, Detailseite, Formulare, Routing | Dokumentenansicht, Upload-UI |

**Bei nur drei Personen:** C geht in B auf — Auth und Backend sind dieselbe Codebasis.

**Bei zwei starken React-Leuten:** D aufteilen in *Übersicht + Suche* und
*Detailseite + Formulare*. Unterschiedliche Routen, unterschiedliche Komponenten, wenig
Merge-Konflikte.

## Die zwei Abhängigkeiten, die uns ausbremsen können

**1. Das Frontend braucht Endpunkte, die es noch nicht gibt.**
Gegenmaßnahme: Am Montag zuerst die API-Form festlegen — das JSON für einen Patienten
gemeinsam aufschreiben. Danach baut D gegen ein fest hinterlegtes Array und tauscht auf
`fetch` um, sobald B liefert. Eine halbe Stunde am Montag verschafft zwei Leuten zwei Tage
paralleles Arbeiten.

**2. Geschützte Routen blockieren alle anderen.**
Entweder steht der Token-Flow bis **Dienstag**, oder die Patienten-Endpunkte entstehen
zunächst ungeschützt und werden am Ende der Woche in einem Durchgang mit
`Depends(get_current_user)` abgesichert. Beides ist in Ordnung. Es am Donnerstag zufällig
zu merken, ist es nicht.

## Nicht im Scope

Die wichtigste Liste des Projekts. Ein Dreiwochenprojekt scheitert nicht daran, dass etwas
zu schwer war, sondern daran, dass vier Dinge halb fertig sind.

| Nicht im Scope | Warum |
| -------------- | ----- |
| Terminkalender | Eigenes Produkt mit eigenem Datenmodell. Sieht klein aus, ist es nicht. |
| Abrechnung (GOÄ/EBM) | Fachlich komplex, ohne Domänenwissen nicht sinnvoll umsetzbar |
| e-Rezept / Medikationsplan | Braucht echte Schnittstellen und Zulassung |
| Volltextsuche in Anhängen | Braucht OCR — großer Aufwand, wenig sichtbares Ergebnis |
| Versionierung von Dokumenten | Nachträglich leicht ergänzbar, jetzt nur Ballast |
| Anbindung echter Praxissoftware | Nicht möglich und nicht nötig |

Der Punkt, der erfahrungsgemäß am ehesten wieder aufgemacht wird, ist der
**Terminkalender**. Falls ihn jemand unbedingt will: Bonus für Woche 3, kein Sprint-Inhalt.

## Definition of Done

Ein Issue ist fertig, wenn:

- [ ] die Akzeptanzkriterien im Issue alle erfüllt sind
- [ ] der Code auf `main` gemerged ist (über Pull Request, nicht direkt gepusht)
- [ ] jemand anderes es einmal lokal ausprobiert hat
- [ ] `docker compose up` danach weiterhin durchläuft

## Arbeitsweise

- **Branch pro Issue**, Pull Request nach `main`, ein anderes Teammitglied schaut drauf.
  Kein direkter Push auf `main`.
- **Ein Issue gleichzeitig pro Person** in der Spalte *In Arbeit*. Diese eine Regel
  verhindert vier halbfertige Branches am Freitagmorgen.
- **Ein Issue = maximal ein Tag.** Was länger dauert, sind zwei Issues. Nur so hat das
  Daily Stand-up jeden Tag etwas zu berichten.
- **Projekttagebuch** in der README täglich vor Feierabend ergänzen.

## Offene Punkte für Montag

1. **Wer übernimmt welchen Strang?** Nur C ist vorbelegt.
2. **Rollen ja oder nein?** Vorschlag: Sprint 1 ohne, siehe ADR-0004.
3. **Hosting.** Docker Compose ist gesetzt und reicht als Abgabestand. Deployment ist ein
   Sprint-2-Ziel, Zielplattform noch offen — AWS wäre der Lehrplan-Weg, ist aber nicht
   gesetzt.
4. **Kann ein Befund aus drei gescannten Seiten bestehen?** Aktuelles Modell sagt: ein
   Dokument hat höchstens einen Anhang, drei Seiten wären drei Dokumente. Falls das nicht
   passt, muss das Modell vor Sprint 2 angepasst werden.
5. **Dokumenttypen.** Vorschlag: Befund, Arztbrief, Laborwert, Sonstiges.
6. **Issue-Tracker.** Vorschlag GitHub Issues statt Jira — der Tutor erwartet die
   Dokumentation ohnehin in GitHub, zwei Systeme bedeuten doppelte Pflege.
