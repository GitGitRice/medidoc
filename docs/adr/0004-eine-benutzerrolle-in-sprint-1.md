---
status: proposed
---

# Sprint 1 kennt nur eine Benutzerrolle

Realistisch wäre eine Unterscheidung zwischen Arzt und MFA — in einer echten Praxis pflegt
die MFA Stammdaten, der Arzt schreibt Befunde. Für Sprint 1 ist trotzdem jeder angemeldete
Benutzer gleichberechtigt, weil ein Rechtemodell die Testfläche jeder Funktion verdoppelt
und jede Rollenprüfung eine Stelle ist, an der die Anwendung in der Vorführung falsch
reagieren kann. Rollen sind additiv nachrüstbar, sobald die Authentifizierung steht.

## Falls wir Rollen doch einführen

Dann zuerst die Tabelle "wer darf was" gemeinsam festlegen — zwei Spalten, wenige Zeilen,
von allen abgenommen — und erst danach implementieren. Ohne diese Abstimmung bauen zwei
Leute zwei verschiedene Rechtemodelle.
