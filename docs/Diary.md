# Projekttagebuch

Täglicher Stand pro Person. Neueste Einträge oben.

| Datum | Person | Ergebnisse |
| ----- | ------ | ---------- |
| 2026-08-05 | Steven Tanu | Auth-Strang abgeschlossen und über `feature/auth` nach `develop` gemerged (PR #31): Patienten-Endpunkte am Router mit `get_current_user` abgesichert, `DELETE` zusätzlich mit `require_roles(Role.ADMIN)` (Issue #15), Login-Seite und `AuthContext` mit `ProtectedRoute`, Token in `localStorage` und Wiederherstellung über `GET /auth/me` (Issue #17). Dazu GitHub Actions für beide Test-Suiten. Danach aufgeräumt (Issue #35): `npm run build` als CI-Schritt, veraltete Stellen in `docs/patients-api.md` und im Patienten-Router korrigiert, Tagebuch auf diese Datei vereinheitlicht. **Hindernis/offen:** `main` und `develop` sind auf GitHub nicht geschützt — ADR-0006 verlangt Pull Requests, erzwungen wird es bisher nicht. |
| 2026-08-04 | Steven Tanu | `POST /auth/login` umgesetzt: JWT mit `sub`, `role` und acht Stunden Laufzeit, einheitliches `401` für unbekannte E-Mail, falsches Passwort und deaktivierten Benutzer (Issue #14). Dazu das erste Test-Setup im Backend (pytest gegen SQLite im Speicher, 10 Tests), E-Mails jetzt case-insensitiv, fehlende Variablen in `.env.example` ergänzt und Gitflow als Branching-Modell dokumentiert (ADR-0006). |
| 2026-08-03 | Dominik Fischer | PostgreSQL-Service mit Docker Compose, persistentem Volume, `.env.example` und Healthcheck umgesetzt und die Datenpersistenz nach einem Container-Neustart geprüft (Issue #2, PR #23). |
| 2026-08-03 | Steven Tanu | Backend-Grundgerüst, Benutzermodell mit bcrypt-Hashing und Seed umgesetzt (Issue #13, PR #24). |
