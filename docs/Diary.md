# Projekttagebuch

Täglicher Stand pro Person. Neueste Einträge oben.

| Datum | Person | Ergebnisse |
| ----- | ------ | ---------- |
| 2026-08-04 | Steven Tanu | `POST /auth/login` umgesetzt: JWT mit `sub`, `role` und acht Stunden Laufzeit, einheitliches `401` für unbekannte E-Mail, falsches Passwort und deaktivierten Benutzer (Issue #14). Dazu das erste Test-Setup im Backend (pytest gegen SQLite im Speicher, 10 Tests), E-Mails jetzt case-insensitiv, fehlende Variablen in `.env.example` ergänzt und Gitflow als Branching-Modell dokumentiert (ADR-0006). |
| 2026-08-03 | Dominik Fischer | PostgreSQL-Service mit Docker Compose, persistentem Volume, `.env.example` und Healthcheck umgesetzt und die Datenpersistenz nach einem Container-Neustart geprüft (Issue #2, PR #23). |
| 2026-08-03 | Steven Tanu | Backend-Grundgerüst, Benutzermodell mit bcrypt-Hashing und Seed umgesetzt (Issue #13, PR #24). |
