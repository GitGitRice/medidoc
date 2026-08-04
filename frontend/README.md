# MediDoc frontend

Minimaler React-Client für die Anmeldung aus Issue #17. Farben, Branding und das
endgültige Layout sind bewusst noch nicht festgelegt.

## Lokal starten

Voraussetzung: Das Backend läuft auf `http://localhost:8000`.

```bash
npm install
npm run dev
```

Eine andere Backend-Adresse kann über `VITE_API_URL` gesetzt werden. Die erwarteten
Requests und Responses stehen in [`../docs/auth-api.md`](../docs/auth-api.md).

## Tests

```bash
npm test
```

Läuft gegen jsdom, ohne Backend — die Netzwerkschicht wird gemockt.

## Aufbau

- `src/api.js` — der einzige Ort, an dem `fetch` steht. Kennt kein React.
- `src/auth/AuthContext.jsx` — hält Token und Benutzer und stellt `apiFetch` bereit.
- `src/auth/ProtectedRoute.jsx` — schickt ohne Anmeldung auf `/login`.

Geschützte Endpunkte werden über `apiFetch` aus `useAuth()` angesprochen, nicht über
`fetch` oder `apiRequest` direkt. Nur dieser Weg hängt den Token an und meldet bei
einem `401` ab — die Regel dazu steht in [`../docs/auth-api.md`](../docs/auth-api.md).
