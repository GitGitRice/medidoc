# Patienten — API-Vertrag

> **Zweck:** Damit Frontend und Backend parallel arbeiten können. Diese Datei ist die
> verbindliche Form. Ändert sich hier etwas, wird es hier geändert und im Daily gesagt.
>
> **Sprache:** Code und API sind englisch, deutsch ist nur die Oberfläche im Frontend.
> JSON-Keys sind also englisch.
>
> Auth-Vertrag: [auth-api.md](./auth-api.md).
> Rollenmodell: [ADR-0005](./adr/0005-rollen-admin-und-staff.md).
> Fachliche Begriffe: [CONTEXT.md](../CONTEXT.md).

Basis-URL lokal: `http://localhost:8000`

## Kurzfassung

- Der **Patient** ist die zentrale Einheit. Stammdaten liegen in PostgreSQL, Dokumente ab
  Sprint 2 in MongoDB ([ADR-0002](./adr/0002-postgres-fuer-stammdaten-mongodb-fuer-dokumente.md)).
- Pflicht sind nur `first_name`, `last_name`, `date_of_birth`. Alles andere darf fehlen.
- `GET /patients` liefert **keine nackte Liste**, sondern `{ items, total, limit, offset }`.
- **Alle Endpunkte verlangen einen Token**, `DELETE` zusätzlich die Rolle `admin` — siehe
  [Absicherung](#absicherung) unten.

| Methode | Pfad | Zweck | Erfolg |
| ------- | ---- | ----- | ------ |
| `GET` | `/patients` | Patientenübersicht, durchsuchbar und seitenweise | `200` |
| `POST` | `/patients` | Patient anlegen | `201` |
| `GET` | `/patients/{id}` | Stammdaten eines Patienten | `200` |
| `PATCH` | `/patients/{id}` | einzelne Felder ändern | `200` |
| `DELETE` | `/patients/{id}` | endgültig löschen | `204` |

## Die Stammdaten

| Feld | Typ | Pflicht | Hinweis |
| ---- | --- | ------- | ------- |
| `id` | int | — | vom Server vergeben |
| `first_name` | str | **ja** | wird getrimmt, darf nicht leer sein |
| `last_name` | str | **ja** | wird getrimmt, darf nicht leer sein |
| `date_of_birth` | date | **ja** | `YYYY-MM-DD`, nicht in der Zukunft |
| `email` | str \| null | nein | wird **nicht** auf Form geprüft, siehe offene Punkte |
| `phone` | str \| null | nein | freies Format, `"030 1234567"` wie `"0171 2223344"` |
| `street` | str \| null | nein | Straße mit Hausnummer in einem Feld |
| `postal_code` | str \| null | nein | als String, nicht als Zahl — führende Null |
| `city` | str \| null | nein | |
| `insurance_provider` | str \| null | nein | Name der Kasse |
| `insurance_number` | str \| null | nein | **eindeutig**, wenn gesetzt |
| `insurance_type` | `statutory` \| `private` \| null | nein | gesetzlich / privat |
| `notes` | str \| null | nein | Freitext |
| `created_at` | datetime | — | vom Server, UTC |
| `updated_at` | datetime | — | vom Server, wandert bei jedem `PATCH` |

Nur drei Pflichtfelder — Absicht: Am Empfang steht der Name, die Karte wird vielleicht
erst später eingelesen. **Ein Patient ohne Telefonnummer und ohne Versicherung ist ein
gültiger Patient.** Das Frontend muss überall mit `null` rechnen; in den Testdaten gibt es
solche Fälle bewusst.

`insurance_number` ist eindeutig, aber optional. PostgreSQL lässt in einem Unique-Index
beliebig viele `NULL` zu: Beliebig viele Patienten ohne Nummer sind erlaubt, zwei
Patienten mit derselben Nummer nicht.

## GET /patients

Die Patientenübersicht. Sortiert nach Nachname, dann Vorname, dann `id` — die
`id` am Ende macht die Reihenfolge bei Namensgleichheit stabil, sonst springen
Zeilen beim Blättern.

**Request**

```
GET /patients?q=hartmann&limit=25&offset=0
```

| Parameter | Standard | Hinweis |
| --------- | -------- | ------- |
| `q` | — | sucht in Vorname, Nachname und Versichertennummer |
| `limit` | `25` | 1–100, darüber `422` |
| `offset` | `0` | |

**Response `200`**

```json
{
  "items": [
    {
      "id": 5,
      "first_name": "Friedrich",
      "last_name": "Hartmann",
      "date_of_birth": "1951-09-08",
      "insurance_number": "P100200300"
    },
    {
      "id": 6,
      "first_name": "Lena",
      "last_name": "Hartmann",
      "date_of_birth": "1996-04-17",
      "insurance_number": "P100200301"
    }
  ],
  "total": 3,
  "limit": 25,
  "offset": 0
}
```

Die Zeilen sind bewusst schmal — genau die fünf Felder, die die Tabelle anzeigt. Wer mehr
braucht, öffnet den Patienten einzeln. Damit bleibt die Übersicht klein, auch wenn ein
Patient später viele Felder hat.

`total` ist die Trefferzahl **ohne** `limit` und `offset`. Daraus baut das Frontend die
Seitenzahl und „3 Patienten gefunden". Im Beispiel: drei Treffer, zwei davon abgebildet,
weil das dritte Ergebnis abgeschnitten wurde.

### Die Suche

`q` trifft in **Vorname, Nachname oder Versichertennummer**, Groß- und Kleinschreibung
egal, Teiltreffer erlaubt.

Mehrere Wörter werden **UND**-verknüpft, jedes einzelne darf in einem beliebigen der drei
Felder treffen. Die Reihenfolge ist also egal:

| Eingabe | Findet |
| ------- | ------ |
| `hartmann` | alle Hartmanns |
| `lena hartmann` | Lena Hartmann |
| `hartmann lena` | dasselbe |
| `P1002003` | beide Patienten mit dieser Nummer als Anfang |

`%` und `_` werden maskiert und suchen sich selbst — eine Suche nach `%` liefert keine
Treffer, nicht alle Patienten.

Nicht gesucht wird in Adresse, Notizen und Kasse. Falls das gebraucht wird: sagen, ist ein
Zweizeiler.

## POST /patients

**Request**

```json
POST /patients
Content-Type: application/json

{
  "first_name": "Doku",
  "last_name": "Beispiel",
  "date_of_birth": "1988-02-29",
  "insurance_provider": "AOK Nordost",
  "insurance_number": "Q000000001",
  "insurance_type": "statutory"
}
```

**Response `201`**

```json
{
  "first_name": "Doku",
  "last_name": "Beispiel",
  "date_of_birth": "1988-02-29",
  "email": null,
  "phone": null,
  "street": null,
  "postal_code": null,
  "city": null,
  "insurance_provider": "AOK Nordost",
  "insurance_number": "Q000000001",
  "insurance_type": "statutory",
  "notes": null,
  "id": 201,
  "created_at": "2026-08-03T18:47:10.919290Z",
  "updated_at": "2026-08-03T18:47:10.919297Z"
}
```

Nicht gesetzte Felder kommen als `null` zurück, nicht als fehlender Schlüssel. Das
Frontend muss also nicht zwischen „nicht da" und „leer" unterscheiden.

## GET /patients/{id}

Liefert denselben vollständigen Patienten wie `POST`.

```json
{
  "first_name": "Max",
  "last_name": "Mustermann",
  "date_of_birth": "1978-03-14",
  "email": "max.mustermann@example.test",
  "phone": "030 1234567",
  "street": "Hauptstraße 12",
  "postal_code": "10115",
  "city": "Berlin",
  "insurance_provider": "AOK Nordost",
  "insurance_number": "A123456789",
  "insurance_type": "statutory",
  "notes": null,
  "id": 1,
  "created_at": "2026-08-03T18:47:09.141101Z",
  "updated_at": "2026-08-03T18:47:09.141108Z"
}
```

## PATCH /patients/{id}

Ändert **nur die geschickten Felder**. Weggelassene bleiben, wie sie sind — das Formular
kann ein einzelnes Feld schicken und muss den Patienten nicht zurückspielen.

```json
PATCH /patients/1
Content-Type: application/json

{ "city": "Hamburg" }
```

Antwort ist der vollständige Patient mit gewandertem `updated_at`.

Die drei Pflichtfelder dürfen **weggelassen**, aber nicht auf `null` gesetzt werden —
`{"last_name": null}` ergibt `422`. Wer ein optionales Feld leeren will, schickt dagegen
ganz normal `null`: `{"phone": null}` löscht die Telefonnummer.

`PUT` gibt es nicht. Bei dreizehn Feldern, von denen zehn optional sind, ist ein
vollständiges Ersetzen die fehleranfälligere Form — ein vergessenes Feld löscht Daten.

## DELETE /patients/{id}

`204`, kein Rumpf. Der Patient ist danach weg — **kein Soft-Delete, kein Papierkorb.**

Löschen ist laut [ADR-0005](./adr/0005-rollen-admin-und-staff.md) die einzige Aktion, die
Daten unwiederbringlich entfernt, und deshalb die einzige, die eine Rolle prüft. Das
Frontend sollte vorher zurückfragen.

## Fehler

| Status | Wann | Rumpf |
| ------ | ---- | ----- |
| `404` | ID gibt es nicht | `{ "detail": "Patient nicht gefunden" }` |
| `409` | Versichertennummer schon vergeben | `{ "detail": "Diese Versichertennummer ist bereits vergeben" }` |
| `422` | Validierung | FastAPI-Standardform, siehe unten |
| `401` / `403` | sobald Auth steht, siehe [auth-api.md](./auth-api.md) | |

`409` kommt bei `POST` und bei `PATCH`. Beim `PATCH` ist die **eigene** Nummer erlaubt —
ein Patient kollidiert nicht mit sich selbst.

Ein `422` listet jedes fehlerhafte Feld einzeln auf. `loc` endet auf dem Feldnamen, damit
das Formular die Meldung an der richtigen Stelle anzeigen kann:

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "first_name"],
      "msg": "Value error, darf nicht leer sein",
      "input": ""
    },
    {
      "type": "value_error",
      "loc": ["body", "date_of_birth"],
      "msg": "Value error, darf nicht in der Zukunft liegen",
      "input": "2099-01-01"
    }
  ]
}
```

## Absicherung

Mit `get_current_user` und `require_roles` gilt:

| Endpunkt | Verlangt |
| -------- | -------- |
| `GET`, `POST`, `PATCH` auf `/patients` | gültigen Token |
| `DELETE /patients/{id}` | gültigen Token **und** Rolle `admin` |

Das ist die einzige Stelle im Sprint 1, die eine Rolle prüft. Für das Frontend gilt:
`401` → Token verwerfen und zur Login-Seite, `403` → Meldung anzeigen, **kein** Logout.

Der Löschen-Button darf für `staff` ausgeblendet werden. Das ist Bedienkomfort, keine
Absicherung — durchgesetzt wird im Backend.

## Für das Frontend

```js
const base = "http://localhost:8000";

// Übersicht mit Suche und Blättern
const params = new URLSearchParams({ q: suchbegriff, limit: 25, offset: seite * 25 });
const res = await fetch(`${base}/patients?${params}`);
const { items, total } = await res.json();

// Einzelnes Feld ändern
await fetch(`${base}/patients/${id}`, {
  method: "PATCH",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ city: "Hamburg" }),
});
```

An jeden Request kommt der `Authorization`-Header mit dem Bearer-Token, genau wie in
[auth-api.md](./auth-api.md) beschrieben.

Leere Suche einfach weglassen: `?q=` und gar kein `q` verhalten sich gleich.

## Testdaten

200 frei erfundene Patienten liegen als JSON in
[`backend/testdata/patients.json`](../backend/testdata/patients.json) — dieselbe Form wie
der Rumpf von `POST /patients`. **Das Frontend kann die Datei direkt als Mock benutzen**,
solange es noch nicht gegen die API baut.

Anlegen aus `backend/`:

```bash
python -m app.seed                 # alle 200
python -m app.seed --patients 50   # nur die ersten 50
```

Mehrfach ausführbar, Vorhandenes wird übersprungen. Die ersten sieben Datensätze sind von
Hand geschrieben — Max Mustermann, die Hartmanns, ein Kind, ein Patient ganz ohne
Versicherung. Auf die beziehen sich die Beispiele in dieser Datei.

Die restlichen 193 sind erzeugt und decken bewusst die unbequemen Fälle ab: Umlaute und
türkische Zeichen in Namen (`Yılmaz`, `Özdemir`), Familien unter derselben Adresse,
Patienten ohne Adresse, ohne E-Mail oder ohne Versicherung, Geburtsdaten von 1930 bis 2025.

| | Anzahl |
| - | ------ |
| Datensätze | 200 |
| davon privat versichert | 27 |
| ohne Versicherungsangabe | 9 |
| ohne Adresse | 31 |
| ohne E-Mail | 64 |
| mit Notiz | 41 |

Reine Testdaten, wie das ganze Projekt — keine echten Patientendaten.

## Offene Punkte

- **`/patients` oder `/patienten`?** [CONTEXT.md](../CONTEXT.md) und
  [ADR-0005](./adr/0005-rollen-admin-und-staff.md) legen fest, dass Code und API
  durchgehend englisch sind. Die Beispiele in [auth-api.md](./auth-api.md) schrieben
  ursprünglich `/patienten`; sie sind auf `/patients` gezogen worden, damit die Doku sich
  nicht widerspricht. **Gehört trotzdem einmal ins Daily bestätigt** — ADR-0005 ist als
  angenommene Entscheidung nicht nachträglich geändert worden und nennt dort weiterhin
  `/patienten`.
- **`email` wird nicht auf Form geprüft**, nur als String gespeichert. Für echte Prüfung
  müsste `email-validator` in die `requirements.txt`.
- **Kein Sortierparameter.** Sortiert wird immer nach Nachname. Falls die Tabelle
  klickbare Spaltenköpfe bekommen soll, braucht es ein `sort=`.

## Nicht enthalten

Zusammenführen von Dubletten, Archivieren statt Löschen, Änderungshistorie, Export.
Nichts davon ist für die Vorführung nötig. Dokumente in der Akte sind Sprint 2 und
bekommen einen eigenen Vertrag.
