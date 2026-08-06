# Patienten — API-Vertrag

> **Zweck:** Damit Frontend und Backend parallel arbeiten können. Diese Datei ist die
> verbindliche Form. Ändert sich hier etwas, wird es hier geändert und im Daily gesagt.
>
> **Sprache:** Code und API sind englisch — Pfad, Query-Parameter und JSON-Keys
> (`/patients`, `?q=`, `first_name`). Siehe [Namensgebung](#namensgebung) unten.
>
> Auth-Vertrag: [auth-api.md](./auth-api.md).
> Rollenmodell: [ADR-0005](./adr/0005-rollen-admin-und-staff.md).
> Fachliche Begriffe: [CONTEXT.md](../CONTEXT.md).

Basis-URL lokal: `http://localhost:8000`

## Kurzfassung

- Der **Patient** ist die zentrale Einheit. Stammdaten liegen in PostgreSQL, Dokumente ab
  Sprint 2 in MongoDB ([ADR-0002](./adr/0002-postgres-fuer-stammdaten-mongodb-fuer-dokumente.md)).
- **Jeder Endpunkt verlangt einen gültigen Token.** `DELETE` verlangt zusätzlich `admin`.
- Pflicht sind nur `first_name`, `last_name`, `date_of_birth`. Alles andere darf fehlen.
- `GET /patients` liefert **keine nackte Liste**, sondern `{ items, total, limit, offset }`.
- Jede Fehlerantwort hat dieselbe Form: `status` und `message`.

| Methode | Pfad | Zweck | Erfolg | Verlangt |
| ------- | ---- | ----- | ------ | -------- |
| `GET` | `/patients` | Patientenübersicht, durchsuchbar und seitenweise | `200` | Token |
| `POST` | `/patients` | Patient anlegen | `201` | Token |
| `GET` | `/patients/{id}` | Stammdaten eines Patienten | `200` | Token |
| `PATCH` | `/patients/{id}` | einzelne Felder ändern | `200` | Token |
| `DELETE` | `/patients/{id}` | endgültig löschen | `204` | Token + `admin` |

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

Die Patientenübersicht. Sortiert nach Nachname, dann Vorname, dann `id` — die `id` am Ende
macht die Reihenfolge bei Namensgleichheit stabil, sonst springen Zeilen beim Blättern.

**Request**

```
GET /patients?q=hartmann&limit=25&offset=0
Authorization: Bearer <token>
```

| Parameter | Standard | Hinweis |
| --------- | -------- | ------- |
| `q` | — | filtert nach Vorname, Nachname und Versichertennummer |
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

> **`GET /patients` liefert eine Seite, nicht alle Datensätze.** Ohne `limit` sind das die
> ersten 25. Wer wirklich alle will, blättert über `offset` — `limit` ist bei 100 gedeckelt,
> damit ein Tippfehler nicht die ganze Tabelle zieht.

### Die Suche

`q` trifft in **Vorname, Nachname oder Versichertennummer**, Groß- und Kleinschreibung
egal, Teiltreffer erlaubt.

Mehrere Wörter werden **UND**-verknüpft, jedes einzelne darf in einem beliebigen der drei
Felder treffen. Die Reihenfolge ist also egal:

| Eingabe | Findet |
| ------- | ------ |
| `hartmann` | alle Hartmanns |
| `HARTMANN` | dasselbe |
| `lena hartmann` | Lena Hartmann |
| `hartmann lena` | dasselbe |
| `P1002003` | beide Patienten mit dieser Nummer als Anfang |

**Kein Treffer ist kein Fehler.** Die Antwort ist `200` mit leerer Liste:

```json
{ "items": [], "total": 0, "limit": 25, "offset": 0 }
```

`?q=` ohne Wert verhält sich wie gar kein `q`.

`%` und `_` werden maskiert und suchen sich selbst — eine Suche nach `%` liefert keine
Treffer, nicht alle Patienten.

Nicht gesucht wird in Adresse, Notizen und Kasse. Falls das gebraucht wird: sagen, ist ein
Zweizeiler.

**Eine bekannte Grenze:** Groß-/Kleinschreibung ist über Umlaute hinweg egal (`özdemir`
findet `Özdemir`), aber `YILMAZ` mit gewöhnlichem `I` findet **nicht** `Yılmaz` mit
punktlosem `ı`. Das sind verschiedene Zeichen, und nur eine türkische Collation brächte sie
zusammen. Für unseren Scope in Ordnung, hier nur festgehalten, damit es niemanden überrascht.

## POST /patients

**Request**

```json
POST /patients
Authorization: Bearer <token>
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
  "created_at": "2026-08-04T09:12:44.919290Z",
  "updated_at": "2026-08-04T09:12:44.919297Z"
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
  "created_at": "2026-08-04T09:12:09.141101Z",
  "updated_at": "2026-08-04T09:12:09.141108Z"
}
```

## PATCH /patients/{id}

Ändert **nur die geschickten Felder**. Weggelassene bleiben, wie sie sind — das Formular
kann ein einzelnes Feld schicken und muss den Patienten nicht zurückspielen.

```json
PATCH /patients/1
Authorization: Bearer <token>
Content-Type: application/json

{ "city": "Hamburg" }
```

Antwort ist der **vollständige** Patient mit gewandertem `updated_at`, nicht nur das
geänderte Feld.

Die drei Pflichtfelder dürfen **weggelassen**, aber nicht auf `null` gesetzt werden —
`{"last_name": null}` ergibt `422`. Wer ein optionales Feld leeren will, schickt dagegen
ganz normal `null`: `{"phone": null}` löscht die Telefonnummer.

Ein leerer Rumpf `{}` ist erlaubt und ändert nichts.

`PUT` gibt es nicht. Bei dreizehn Feldern, von denen zehn optional sind, ist ein
vollständiges Ersetzen die fehleranfälligere Form — ein vergessenes Feld löscht Daten.

## DELETE /patients/{id}

`204`, kein Rumpf. Der Patient ist danach weg — **kein Soft-Delete, kein Papierkorb.**

**Verlangt die Rolle `admin`.** Für `staff` kommt `403`, und der Patient bleibt unangetastet.

Löschen ist laut [ADR-0005](./adr/0005-rollen-admin-und-staff.md) die einzige Aktion, die
Daten unwiederbringlich entfernt, und deshalb die einzige, die eine Rolle prüft. Das
Frontend sollte vorher zurückfragen.

Zweimaliges Löschen ist kein Serverfehler: Der zweite Aufruf findet den Patienten nicht
mehr und antwortet mit `404`.

## Fehler

**Jede** Fehlerantwort hat dieselbe Form — unabhängig von Statuscode und Endpunkt:

```json
{
  "status": 404,
  "message": "Patient mit der ID 999999 wurde nicht gefunden"
}
```

`status` wiederholt den HTTP-Status im Rumpf. Das ist bewusst redundant: In `catch`-Zweigen
und in Logs liegt oft nur noch der geparste Rumpf vor, und dann fehlt sonst genau die
Information, die den Fall einordnet.

`message` ist für Menschen gedacht und kann direkt angezeigt werden. Sie ist deutsch und
nennt, wo möglich, den konkreten Wert — die gesuchte ID, die vergebene Nummer.

> **`detail` ist zusätzlich weiterhin da**, in genau der Form, die FastAPI ohne unser
> Zutun erzeugt hätte. Das ist eine Übergangshilfe für Code, der schon `detail` liest.
> **Neuer Code liest `message`.** Sobald nichts mehr auf `detail` zugreift, fliegt es raus.

| Status | Wann | `message` |
| ------ | ---- | --------- |
| `401` | kein, abgelaufener oder ungültiger Token | `Anmeldung erforderlich` |
| `403` | angemeldet, aber Rolle reicht nicht | `Dazu fehlt dir die Berechtigung` |
| `404` | ID gibt es nicht | `Patient mit der ID 42 wurde nicht gefunden` |
| `409` | Versichertennummer schon vergeben | `Die Versichertennummer A123456789 ist bereits einem anderen Patienten zugeordnet` |
| `422` | Eingabe ungültig | siehe unten |

`409` kommt bei `POST` und bei `PATCH`. Beim `PATCH` ist die **eigene** Nummer erlaubt —
ein Patient kollidiert nicht mit sich selbst.

Bei `404` und `409` schlägt `404` vor: Wer einen nicht existierenden Patienten ändern will,
bekommt `404`, auch wenn die mitgeschickte Nummer vergeben wäre.

### 422 — welches Feld ist schuld

Bei Validierungsfehlern kommt `errors` dazu, ein Eintrag pro beanstandetem Feld. `message`
fasst zusammen und **nennt die Feldnamen**, damit die Meldung auch ohne Auswertung von
`errors` etwas taugt:

```json
POST /patients   { "first_name": "Max" }
```

```json
{
  "status": 422,
  "message": "Pflichtfelder fehlen: last_name, date_of_birth",
  "errors": [
    { "field": "last_name", "message": "Feld ist erforderlich" },
    { "field": "date_of_birth", "message": "Feld ist erforderlich" }
  ]
}
```

`field` ist der Feldname ohne das führende `body`/`query` — direkt der Schlüssel, unter dem
das Formular sein Eingabefeld führt.

Andere Beispiele:

| Eingabe | `message` |
| ------- | --------- |
| `{"first_name": "   "}` | `Ungültige Eingabe für 'first_name': darf nicht leer sein` |
| `date_of_birth: "2099-01-01"` | `Ungültige Eingabe für 'date_of_birth': darf nicht in der Zukunft liegen` |
| `date_of_birth: "14.03.1978"` | `Ungültige Eingabe für 'date_of_birth': Muss ein Datum im Format JJJJ-MM-TT sein` |
| `PATCH {"last_name": null}` | `Ungültige Eingabe für 'last_name': darf nicht auf null gesetzt werden` |
| `?limit=1000` | `Ungültige Eingabe für 'limit': Wert ist zu groß` |

## Für das Frontend

```js
const base = "http://localhost:8000";
const auth = { Authorization: `Bearer ${token}` };

// Übersicht mit Suche und Blättern
const params = new URLSearchParams({ q: suchbegriff, limit: 25, offset: seite * 25 });
const res = await fetch(`${base}/patients?${params}`, { headers: auth });
const { items, total } = await res.json();

// Einzelnes Feld ändern
await fetch(`${base}/patients/${id}`, {
  method: "PATCH",
  headers: { ...auth, "Content-Type": "application/json" },
  body: JSON.stringify({ city: "Hamburg" }),
});

// Fehler einheitlich auspacken
if (!res.ok) {
  const { message } = await res.json();
  zeigeMeldung(message);
}
```

`401` heißt: Token verwerfen und zur Login-Seite. `403` heißt: Meldung anzeigen, **kein**
Logout. Die Unterscheidung steht in [auth-api.md](./auth-api.md).

Der Löschen-Button darf für `staff` ausgeblendet werden. Das ist Bedienkomfort, keine
Absicherung — durchgesetzt wird im Backend.

## Testdaten

200 frei erfundene Patienten liegen als JSON in
[`backend/testdata/patients.json`](../backend/testdata/patients.json) — dieselbe Form wie
der Rumpf von `POST /patients`. **Das Frontend kann die Datei direkt als Mock benutzen.**

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

## Automatisierte Tests

Jeder Punkt in dieser Datei hat einen Test in
[`backend/tests/test_patients_api.py`](../backend/tests/test_patients_api.py), gegliedert
nach Endpunkt. Aus `backend/`:

```bash
python -m pytest
```

Die Tests laufen gegen SQLite im Speicher und brauchen kein laufendes Docker. Was sich
damit **nicht** prüfen lässt, steht als Kommentar im Testkopf: SQLite ignoriert die
Groß-/Kleinschreibung nur bei ASCII, die Umlaut-Fälle der Suche sind also nur gegen
Postgres aussagekräftig.

## Namensgebung

Pfad, Query-Parameter und JSON-Keys sind englisch (`/patients`, `?q=`, `first_name`).
Deutsch sind Kommentare, diese Doku und die Oberfläche im Frontend. Dieselbe Regel steht in
[auth-api.md](./auth-api.md) und in [ADR-0005](./adr/0005-rollen-admin-und-staff.md).

Zwischenzeitlich standen hier `/patienten` und `?suche=`. Der Weg zurück ist bewusst: eine
Regel, die für die Hälfte der API gilt, ist keine Regel, und die Mischung hätte bei jedem
neuen Endpunkt wieder verhandelt werden müssen.

ADR-0005 nennt im Fließtext weiterhin `/patienten`. Eine angenommene Entscheidung wird
nicht nachträglich umgeschrieben — verbindlich sind der Code und diese Datei.

## Offene Punkte

- **`email` wird nicht auf Form geprüft**, nur als String gespeichert. Für echte Prüfung
  müsste `email-validator` in die `requirements.txt`.
- **Kein Sortierparameter.** Sortiert wird immer nach Nachname. Falls die Tabelle
  klickbare Spaltenköpfe bekommen soll, braucht es ein `sort=`.
- **`detail` in Fehlerantworten** ist Übergangsballast und soll raus, sobald das Frontend
  nur noch `message` liest.

## Nicht enthalten

Zusammenführen von Dubletten, Archivieren statt Löschen, Änderungshistorie, Export.
Nichts davon ist für die Vorführung nötig. Dokumente in der Akte sind Sprint 2 und
bekommen einen eigenen Vertrag.
