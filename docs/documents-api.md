# Dokumente — API-Vertrag

> **Zweck:** Dokumente in der Akte eines Patienten anlegen, auflisten, ändern und löschen. Diese
> Datei ist die verbindliche Form. Ändert sich hier etwas, wird es hier geändert und im
> Daily gesagt.
>
> Patienten-API: [patients-api.md](./patients-api.md).
> Auth-Vertrag: [auth-api.md](./auth-api.md).
> Warum MongoDB: [ADR-0002](./adr/0002-postgres-fuer-stammdaten-mongodb-fuer-dokumente.md).

Basis-URL lokal: `http://localhost:8000`

## Kurzfassung

- **Jeder Endpunkt verlangt einen gültigen Token.** Nur `DELETE` verlangt zusätzlich `admin` —
  Anlegen und Ändern darf auch `staff`.
- Angelegt wird **multipart**, nicht JSON — anders reist ein Anhang nicht.
- **Der Anhang ist optional.** Ein Dokument ohne Anhang ist gültig.
- **Höchstens 20 MB** je Anhang. Darüber `413`, geprüft beim Schreiben.
- Ein Dokument gehört immer zu genau einem Patienten. Gibt es den nicht, kommt `404`.

| Methode | Pfad | Zweck | Erfolg | Verlangt |
| ------- | ---- | ----- | ------ | -------- |
| `POST` | `/docs/{patient_id}` | Dokument anlegen | `201` | Token |
| `GET` | `/docs/{patient_id}?q=&limit=&offset=` | Dokumente auflisten | `200` | Token |
| `PATCH` | `/docs/{patient_id}/{document_id}` | Angaben ändern | `200` | Token |
| `DELETE` | `/docs/{patient_id}/{document_id}` | Dokument löschen | `204` | Token + `admin` |

## Namensgebung

Wie in [patients-api.md](./patients-api.md#namensgebung): **Pfad, Query-Parameter,
Formularfelder und JSON-Keys sind englisch.** Deutsch sind Kommentare, diese Doku und die
Oberfläche im Frontend.

Für die Fachbegriffe gilt [CONTEXT.md](../CONTEXT.md), und zwar wörtlich. Die Spalte
**Nicht sagen** meint die *deutsche* Prosa — Kommentare, diese Doku, die Oberfläche:

| Begriff | Was gemeint ist | Nicht sagen |
| ------- | --------------- | ----------- |
| **Dokument** | ein Eintrag in der Akte — Angaben plus optional ein Anhang | Datei, Upload, Eintrag |
| **Dokumenttyp** | die Art des Dokuments; bestimmt, welche Felder es hat | Kategorie, Art, Klasse |
| **Anhang** | die angehängte Datei zu einem Dokument | Datei, Attachment, Upload |

Zwei Ausnahmen, und nur diese zwei:

**Englische Bezeichner sind keine deutsche Prosa.** Der JSON-Key heißt `attachment` und die
Klasse `Attachment`, weil oben steht, dass JSON-Keys englisch sind — `attachment` *ist* die
englische Übersetzung von **Anhang** und damit richtig. Verboten ist „Attachment" im
deutschen Satz („das Attachment wird gespeichert"), nicht der Bezeichner. Dasselbe gilt für
`UPLOAD_DIR` und `MAX_UPLOAD_BYTES`: Namen der Ablage, nicht der Fachlichkeit.

**`backend/app/modules/documents/storage.py` redet von *Dateien*.** Dort geht es wirklich um
Bytes auf einem Dateisystem — um Blöcke, Endungen und Pfade —, nicht um den fachlichen
Begriff. Überall sonst im Code heißt er **Anhang**.

## Das Modell

Ein **Dokument** besteht aus zwei Gruppen von Angaben und höchstens einem **Anhang**:

- **Für jeden Typ gleich** — `title`, `description`, `tags`, `source`. Sie machen ein
  Dokument in der Liste auffindbar, unabhängig davon, was es ist.
- **Vom Dokumenttyp abhängig** — `fields`, ein freier Satz Schlüssel/Wert. Ein
  `laborwert` trägt hier andere Angaben als ein `arztbrief`.

Damit ist auch die Begründung aus
[ADR-0002](./adr/0002-postgres-fuer-stammdaten-mongodb-fuer-dokumente.md) wieder tragend:
Die zweite Datenbank rechtfertigt sich über die **Heterogenität der Angaben**. Hätte jedes
Dokument dieselben Felder, gäbe es keinen Grund für MongoDB.

## Wo was liegt

Drei Speicher, jeder für das, was er kann:

| | Wo |
| - | -- |
| Patientenstammdaten | PostgreSQL |
| Angaben zum Dokument (Typ, Titel, Tags, `fields` …) | MongoDB, Collection `documents` |
| Die Bytes eines Anhangs | Docker-Volume unter `UPLOAD_DIR` |

MongoDB speichert **keine Dateien** — das ist der Punkt, den ADR-0002 ausdrücklich
festhält. In der Datenbank steht nur, wo der Anhang liegt.

**MongoDB ist für Dokumente Pflicht, nicht Kür.** Ist `MONGO_URL` leer, antworten die
Dokument-Endpunkte mit `500` — es gibt keinen Rückfall in den Prozessspeicher. Der wäre die
freundlichere und die falsche Antwort: Das Anlegen meldete `201`, der Anhang läge wirklich
auf der Platte, und nach dem nächsten Neustart wäre das Dokument weg, ohne dass irgendwo
etwas schiefgegangen wäre. Der Audit-Trail darf das (ADR-0007) — ein verlorener
Protokolleintrag ist kein verlorener Befund. `docker compose up` setzt `MONGO_URL` selbst;
wer das Backend ohne Compose startet, setzt sie in der `.env`.

## Das Dokument

| Feld | Typ | |
| ---- | --- | - |
| `id` | str | vom Server vergeben, 32 Hex-Zeichen |
| `patient_id` | int | zu welchem Patienten es gehört |
| `document_type` | str | **Pflicht**, der Dokumenttyp — getrimmt und kleingeschrieben |
| `title` | str | **Pflicht**, wird getrimmt, darf nicht leer sein |
| `description` | str \| null | |
| `tags` | str[] | siehe unten |
| `source` | str \| null | woher das Dokument stammt, z. B. `"Radiologie Mitte"` |
| `fields` | object | die typabhängigen Angaben, siehe unten. `{}`, wenn keine |
| `attachment` | object \| null | der Anhang, oder `null` |
| `created_at` | datetime | vom Server, UTC |
| `updated_at` | datetime \| null | `null`, solange nie geändert |

Der **Anhang**, wenn es einen gibt:

| Feld | Typ | |
| ---- | --- | - |
| `attachment.filename` | str \| null | der ursprüngliche Dateiname — **nur als Angabe** |
| `attachment.content_type` | str \| null | was der Browser gemeldet hat |
| `attachment.size_bytes` | int | tatsächlich geschriebene Bytes |

Pflicht sind nur **`document_type` und `title`**. Alles andere darf fehlen — auch der
Anhang.

`attachment` ist ein eigenes Objekt und kein Satz einzelner Felder am Dokument. So drückt
die Antwort aus, was CONTEXT.md sagt: **höchstens einer, und keiner ist gültig.** Als drei
nullbare Felder nebeneinander liesse sich nicht ausdrücken, dass sie nur gemeinsam
vorkommen.

`filename` ist `null`, wenn der Aufrufer keinen Namen mitgeschickt hat. Der Server denkt
sich **keinen** aus: Ein zusammengebautes `<id>.bin` sähe im Frontend aus wie ein echter
Name des Benutzers.

Nicht ausgeliefert werden `stored_as` (der Speicherort) und `created_by`. Der Ablageort
geht von außen niemanden etwas an.

### `document_type`

Wird **getrimmt und kleingeschrieben** — sonst wären `Befund` und `befund` zwei Typen und
eine Liste „alle Befunde" fände nur die Hälfte.

Geprüft wird **nicht** gegen eine feste Liste. CONTEXT.md verlangt ausdrücklich: „Neue
Dokumenttypen sollen ohne Schemaänderung möglich sein." Ein neuer Typ kostet damit keine
Codeänderung.

Üblich sind — als Verabredung, nicht als Zwang (siehe
[sprint-1-plan.md](./sprint-1-plan.md)):

`befund` · `arztbrief` · `laborwert` · `sonstiges`

### `fields`

Die Angaben, die vom Dokumenttyp abhängen. Reisen als **JSON-Objekt in einem Formularfeld**
— ein Multipart-Formular kennt keine verschachtelten Werte:

```
fields={"hb": 13.4, "einheit": "g/dl"}      →      "fields": {"hb": 13.4, "einheit": "g/dl"}
```

| Regel | |
| ----- | - |
| Werte | ein einzelner Wert je Schlüssel — Text, Zahl oder Wahrheitswert |
| keine Bäume | Listen und verschachtelte Objekte ergeben `422` |
| kaputtes JSON | ergibt `422` mit `field: "fields"`, keinen `500` |
| Grenzen | höchstens 50 Angaben, Schlüssel 60 Zeichen, Textwerte 500 Zeichen — darüber `422` |
| leerer Schlüssel | ergibt `422` |
| fehlt | `{}` |

Die Grenzen sollen einen Unfall abfangen, keine Fachlichkeit vorschreiben, die noch
niemand kennt. Überschritten wird **abgelehnt, nicht gekürzt**: Ein stilles Abschneiden
gäbe ein `201` auf einen Wert zurück, in dem hinten etwas fehlt, und die Antwort sähe
genauso aus wie bei einem heilen. In einer Akte ist ein abgeschnittener Wert schlimmer als
ein abgelehnter.

### `tags`

Kommt **kommagetrennt** herein und geht als **Liste** wieder hinaus:

```
tags=MRT, Radiologie, mrt      →      "tags": ["mrt", "radiologie"]
```

Kleingeschrieben und ohne Dubletten, damit `MRT` und `mrt` beim Filtern nicht zwei
Schlagworte sind. Die Reihenfolge der ersten Nennung bleibt erhalten — sonst flackerte die
Liste im Frontend bei jedem Laden. Höchstens 20 Tags, je höchstens 40 Zeichen.

## POST /docs/{patient_id}

**Multipart-Formular**, die Angaben plus optional das Feld `file`:

```
POST /docs/42
Authorization: Bearer <token>
Content-Type: multipart/form-data

document_type=befund
title=Befund MRT
description=Knie links
tags=mrt, radiologie
source=Radiologie Mitte
fields={"koerperregion": "Knie links", "befundet": true}
file=@befund.pdf                      ← optional
```

**Response `201`**

```json
{
  "id": "9f2c1ab34d5e4f7a8b0c1d2e3f4a5b6c",
  "patient_id": 42,
  "document_type": "befund",
  "title": "Befund MRT",
  "description": "Knie links",
  "tags": ["mrt", "radiologie"],
  "source": "Radiologie Mitte",
  "fields": { "koerperregion": "Knie links", "befundet": true },
  "attachment": {
    "filename": "befund.pdf",
    "content_type": "application/pdf",
    "size_bytes": 284913
  },
  "created_at": "2026-08-06T12:54:04.642189Z"
}
```

### Ohne Anhang

CONTEXT.md: „Ein Dokument ohne Anhang ist gültig." Ein Laborwert braucht keinen Scan.

**Das Feld `file` einfach weglassen** — dann entsteht ein Dokument mit `"attachment": null`,
und die Platte wird gar nicht erst angefasst.

> **Weglassen, nicht leer schicken.** Wird `file` mitgeschickt, muss etwas drin sein: Eine
> angehängte Datei mit null Bytes ist ein Versehen und ergibt `422`. Das Frontend hängt das
> Feld also nur an, wenn der Benutzer wirklich etwas ausgewählt hat.

### Die 20-MB-Grenze

Über 20 MB antwortet die API mit **`413`**:

```json
{
  "status": 413,
  "message": "Der Anhang ist größer als 20 MB und wurde nicht gespeichert"
}
```

Geprüft wird **beim Schreiben, nicht danach**. Erst alles einlesen und dann die Länge
messen hieße, dass eine 2-GB-Datei zuerst vollständig im Speicher landet. Stattdessen wird
in 1-MiB-Blöcken gelesen und beim Überschreiten sofort abgebrochen — es bleibt weder ein
Dokument in der Datenbank noch eine angefangene Datei auf der Platte.

> **Das ist die Grenze der Anwendung, nicht die des Servers.** Bis unser Code läuft, hat
> Starlette den Rumpf schon entgegengenommen. Wer eine 5-GB-Datei schickt, wird zwar
> abgewiesen, hat aber vorher Platte belegt. Sobald ein Reverse Proxy davorsteht, gehört
> dort dieselbe Grenze hin (`client_max_body_size` bei nginx). Für den Scope dieses
> Projekts genügt die Prüfung in der Anwendung.

### Der Dateiname wird nie zum Pfad

Er kommt aus dem Browser und darf alles enthalten — `../../../etc/passwd` ebenso wie einen
Patientennamen. Gespeichert wird unter `{UPLOAD_DIR}/{patient_id}/{document_id}`; der
ursprüngliche Name überlebt nur als Angabe `attachment.filename`. Von der Endung wird
höchstens ein harmloses `.pdf` übernommen.

## GET /docs/{patient_id}

```
GET /docs/42?q=mrt&limit=100&offset=0
Authorization: Bearer <token>
```

| Parameter | Standard | |
| --------- | -------- | - |
| `q` | — | filtert nach **Titel oder Beschreibung**, Schreibweise egal, Teiltreffer |
| `limit` | `100` | 1–100, darüber `422` |
| `offset` | `0` | |

**Response `200`** — dieselbe Form wie bei den Patienten:

```json
{
  "items": [ { "id": "9f2c…", "document_type": "befund", "title": "Befund MRT", "…": "…" } ],
  "total": 3,
  "limit": 100,
  "offset": 0
}
```

**Neueste zuerst.** `total` ist die Trefferzahl ohne `limit`/`offset`.

**Kein Treffer ist kein Fehler:** `200` mit `{"items": [], "total": 0, …}`. Das gilt auch
für einen Patienten, der noch gar keine Dokumente hat.

Regex-Sonderzeichen in `q` werden maskiert und suchen sich selbst — `.*` findet nichts,
nicht alles, und eine Klammer bricht die Suche nicht ab.

> `q` durchsucht **Titel und Beschreibung**, nicht `fields`. Die typabhängigen Angaben
> stehen unter frei gewählten Schlüsseln; eine Suche darüber bräuchte erst eine Verabredung,
> welche Schlüssel es gibt. Siehe [Offene Punkte](#offene-punkte).

## PATCH /docs/{patient_id}/{document_id}

Ändert die Angaben eines Dokuments. **JSON, nicht multipart** — anders als beim Anlegen
reist hier kein Anhang mit, und für reine Angaben ist JSON die natürliche Form. Nebeneffekt:
FastAPI prüft den Rumpf selbst, das `422` entsteht ohne Zutun im gewohnten Format.

```json
PATCH /docs/42/9f2c1ab34d5e4f7a8b0c1d2e3f4a5b6c
Authorization: Bearer <token>
Content-Type: application/json

{ "title": "Befund MRT — korrigiert", "tags": "mrt, radiologie, knie" }
```

Antwort ist das **vollständige** Dokument mit gesetztem `updated_at`, nicht nur das
geänderte Feld.

**Weggelassene Felder bleiben unverändert.** Das Formular kann ein einzelnes Feld schicken
und muss das Dokument nicht zurückspielen.

| Feld | Weglassen | `null` | `""` |
| ---- | --------- | ------ | ---- |
| `document_type` | bleibt | **`422`** | **`422`** |
| `title` | bleibt | **`422`** | **`422`** |
| `description`, `source` | bleibt | leert | leert |
| `tags` | bleibt | leert | leert |
| `fields` | bleibt | leert | — |

`document_type` und `title` sind Pflichtangaben des Dokuments. Sie dürfen weggelassen, aber
nicht geleert werden — sonst entstünde über `PATCH` ein Dokument, das über `POST` nie
hätte angelegt werden können.

**`fields` ersetzt vollständig, es wird nicht zusammengeführt.** Wer `{"hb": 12.1}` schickt,
hat danach genau diesen einen Schlüssel. Beim Zusammenführen liesse sich ein einmal
gesetzter Schlüssel nie wieder entfernen.

### Was `PATCH` nicht kann

- **Den Patienten wechseln.** `patient_id` steht nicht im Rumpf-Model; wird es trotzdem
  mitgeschickt, wirkt es nicht. Ein Dokument einem anderen Patienten zuzuordnen ist keine
  Korrektur, sondern eine Verlagerung — dafür gäbe es Löschen und neu Anlegen.
- **Den Anhang austauschen.** Er reist nicht durch JSON. Ein neuer Anhang wäre ein neues
  Dokument oder ein eigener Endpunkt.

### Rollen

**`staff` darf ändern.** Dieselbe Linie wie beim Bearbeiten eines Patienten; wer ein
Dokument anlegen darf, darf einen Tippfehler darin auch korrigieren. Nur das **Löschen**
bleibt `admin` vorbehalten — das ist die Aktion, die Daten unwiederbringlich entfernt.

> [ADR-0005](./adr/0005-rollen-admin-und-staff.md) nennt für `staff` ausdrücklich nur
> „Dokumente lesen und anlegen"; das Ändern steht dort nicht, weil der ADR vor den
> Dokument-Endpunkten geschrieben wurde. **Gehört einmal ins Daily bestätigt.**

### Zeitstempel

`updated_at` ist `null`, solange ein Dokument nie geändert wurde — bewusst nicht mit
`created_at` vorbelegt: „nie geändert" und „heute angelegt und geändert" sind zwei
verschiedene Aussagen, und in einer Akte zählt der Unterschied.

Beide Zeitstempel werden auf **Millisekunden** gekürzt. MongoDB speichert nicht genauer;
ohne das Kürzen gäbe das Anlegen einen `created_at` mit Mikrosekunden zurück, den kein
späterer Aufruf je wieder liefert.

## DELETE /docs/{patient_id}/{document_id}

`204`, kein Rumpf. **Angaben und Anhang sind danach weg** — kein Papierkorb.

**Verlangt `admin`.** [ADR-0005](./adr/0005-rollen-admin-und-staff.md) gibt `staff`
ausdrücklich „Dokumente lesen und anlegen"; Löschen steht dort nicht, und es ist die
Aktion, die Daten unwiederbringlich entfernt. Dieselbe Linie wie beim Löschen eines
Patienten. Für `staff` kommt `403`, und das Dokument bleibt.

Die Patienten-ID im Pfad ist nicht nur Zierde: Ein Dokument lässt sich **nicht** über einen
anderen Patienten löschen — das ergibt `404`, und das Dokument bleibt heil.

Zweimaliges Löschen ist kein Serverfehler: Der zweite Aufruf antwortet mit `404`.

### Wird der Patient gelöscht, geht die Akte mit

`DELETE /patients/{id}` entfernt seither auch **alle Dokumente und Anhänge** dieses
Patienten. Ohne das blieben sie liegen: über die API nicht mehr erreichbar, weil jeder
Dokument-Endpunkt den Patienten voraussetzt, und trotzdem auf der Platte.

Wie viele Dokumente dabei weggeräumt wurden, steht im Audit-Trail am Ereignis
`patient_deleted` unter `detail.documents_removed`.

**Scheitert das Abräumen** — etwa weil MongoDB gerade nicht antwortet oder ein Ordner sich
nicht entfernen lässt —, antwortet die API mit `500`, und der Patient ist trotzdem gelöscht
(Postgres war zuerst dran). Der Trail-Eintrag wird in diesem Fall **trotzdem geschrieben**,
mit `detail.documents_removed: null`. Ab dem Löschen ist er der einzige Beleg, dass es den
Patienten gab; er darf nicht am Aufräumen hängen. `null` heißt „unbekannt" und ist
absichtlich etwas anderes als `0` — das hieße „der Patient hatte keine".

Die `500` deckt **beide Hälften** ab, die Angaben in MongoDB und die Anhänge auf der Platte.
Und die Platte wird auch dann abgeräumt, wenn schon die Angaben nicht wegzubekommen waren:
Der Patient ist zu diesem Zeitpunkt bereits gelöscht, und ohne ihn führt kein Endpunkt mehr
zu seinen Anhängen — blieben die Bytes liegen, fände sie nie wieder jemand.

## Fehler

Dieselbe Form wie überall (`status`, `message`), siehe
[patients-api.md](./patients-api.md#fehler).

| Status | Wann |
| ------ | ---- |
| `401` | kein oder ungültiger Token |
| `403` | `staff` versucht zu löschen |
| `404` | Patient oder Dokument gibt es nicht |
| `413` | Anhang größer als 20 MB |
| `422` | `document_type` oder `title` fehlt/ist leer, `fields` ist kein JSON-Objekt, mitgeschickter Anhang ist leer, `limit` zu groß |

## Für das Frontend

```js
const form = new FormData();
form.append("document_type", "befund");
form.append("title", "Befund MRT");
form.append("tags", "mrt, radiologie");         // kommagetrennt
form.append("source", "Radiologie Mitte");
form.append("fields", JSON.stringify({ koerperregion: "Knie links" }));

// Der Anhang ist optional — das Feld nur anhaengen, wenn wirklich eine Datei
// ausgewaehlt wurde. Ein leeres Feld waere ein Fehler, kein "kein Anhang".
if (file) form.append("file", file);            // aus <input type="file">

const res = await fetch(`${base}/docs/${patientId}`, {
  method: "POST",
  headers: { Authorization: `Bearer ${token}` },  // **kein** Content-Type setzen —
  body: form,                                     // den setzt der Browser mit boundary
});

if (res.status === 413) showMessage((await res.json()).message);
```

`Content-Type` **nicht** von Hand setzen. Der Browser trägt ihn samt `boundary` selbst ein;
wer ihn überschreibt, macht das Formular unlesbar.

Die Größe lässt sich vorab im Browser prüfen (`file.size > 20 * 1024 * 1024`) — das spart
den Upload. Es ist Bedienkomfort, keine Absicherung: Durchgesetzt wird im Backend.

Beim Anzeigen: `attachment` kann `null` sein. Eine Zeile ohne Anhang ist kein Fehlerfall,
sondern ein gültiges Dokument.

## Im Audit-Trail

Anlegen und Löschen werden festgehalten
([logging-monitoring.md](./logging-monitoring.md)) — als `document_created` und
`document_deleted`, mit `document:<id>` und `patient:<id>`.

`document_created` und nicht `document_uploaded`: Ein Dokument entsteht auch ohne Anhang,
hochgeladen wird dabei nichts.

**Weder Dateiname noch Titel landen im Trail.** Beide heißen in der Praxis gern
„Mueller_Befund.pdf" und wären damit genau die Patientenangabe, die dort nicht hingehört.
Aus demselben Grund steht auch `fields` nicht drin — dort landet in der Praxis alles.
Festgehalten werden Dokumenttyp, Größe und Content-Type; die sagen genug, um einen Vorfall
einzuordnen, und der Dokumenttyp ist eine feste Fachkategorie, die nichts über den
Patienten verrät.

## Offene Punkte

- **Es gibt keinen Download.** Die Anforderung nennt Anlegen, Auflisten und Löschen — die
  Bytes sind damit vorerst nur ablegbar, nicht wieder abrufbar. Ein
  `GET /docs/{patient_id}/{document_id}/file` wäre der nächste Schritt und ist klein; er
  muss nur dieselbe Prüfung fahren (Token, Patient, Zugehörigkeit) und den Speicherort
  weiterhin geheim halten.
- **`q` durchsucht `fields` nicht.** Sinnvoll wäre es erst, wenn je Dokumenttyp verabredet
  ist, welche Schlüssel es gibt. Gehört ins Daily.
- **Es gibt keine Liste erlaubter Dokumenttypen.** Das ist Absicht (CONTEXT.md: neue Typen
  ohne Schemaänderung), heißt aber auch: Ein Tippfehler legt einen neuen Typ an. Sobald das
  Frontend eine Auswahl anbietet, ist das praktisch entschärft.
- **Der Pfad `/docs` gehört auch der Swagger-Oberfläche.** FastAPI liefert sie unter dem
  exakten Pfad `/docs` aus, unsere Routen beginnen erst darunter (`/docs/42`) — beides
  läuft nebeneinander, und ein Test wacht darüber. Verwechslungsfrei ist es trotzdem
  nicht, und der übrige Bestand heißt `/patients`. **`/patients/{id}/documents` wäre der
  saubere Zug** und würde nebenbei ausdrücken, dass ein Dokument ohne Patient nicht
  existiert. Gehört ins Daily.
- **Kein Virenscan, keine Typprüfung.** Angehängt werden darf alles. In einer echten
  Praxis wäre beides Pflicht.
- **Keine Vorschau, keine Größenbeschränkung pro Patient.**

## Tests

[`backend/tests/test_documents_api.py`](../backend/tests/test_documents_api.py), gegliedert
nach Endpunkt, dazu eigene Blöcke für Dokumenttyp, typabhängige Angaben, Dokumente ohne
Anhang, die Größenprüfung und die Ablage auf der Platte. Sie laufen gegen den
Speicher-Store und einen temporären Ordner — kein MongoDB, kein Docker.

Der wichtigste Test ist `test_der_dateiname_des_aufrufers_wird_nie_zum_pfad`.

## Testdaten

[`backend/testdata/documents.json`](../backend/testdata/documents.json) füllt die Akten der
ersten sechs Testpatienten — alle vier üblichen Dokumenttypen, mit und ohne Anhang, eines
nur mit Pflichtangaben. Angelegt werden sie mit `python -m app.seed`
([backend/README.md](../backend/README.md)); der Patient steht dort als Versichertennummer
und nicht als `id`, weil die `id` davon abhängt, was vorher in der Tabelle stand.

Die Anhänge sind **Platzhalter**: Name, Typ und Größe stimmen, die Bytes sind ein kurzer
Text. Ausgeliefert werden sie ohnehin nicht — einen Download gibt es noch nicht (siehe
[Offene Punkte](#offene-punkte)).
