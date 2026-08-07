# Dokumente — API-Vertrag

> **Zweck:** Dateien zu einem Patienten hochladen, auflisten und löschen. Diese Datei ist
> die verbindliche Form. Ändert sich hier etwas, wird es hier geändert und im Daily gesagt.
>
> Patienten-API: [patients-api.md](./patients-api.md).
> Auth-Vertrag: [auth-api.md](./auth-api.md).
> Warum MongoDB: [ADR-0002](./adr/0002-postgres-fuer-stammdaten-mongodb-fuer-dokumente.md).

Basis-URL lokal: `http://localhost:8000`

## Kurzfassung

- **Jeder Endpunkt verlangt einen gültigen Token.** `DELETE` verlangt zusätzlich `admin`.
- Hochgeladen wird **multipart**, nicht JSON — anders reist eine Datei nicht.
- **Höchstens 20 MB.** Darüber `413`, geprüft beim Schreiben.
- Ein Dokument gehört immer zu genau einem Patienten. Gibt es den nicht, kommt `404`.

| Methode | Pfad | Zweck | Erfolg | Verlangt |
| ------- | ---- | ----- | ------ | -------- |
| `POST` | `/docs/{patient_id}` | Datei hochladen | `201` | Token |
| `GET` | `/docs/{patient_id}?q=&limit=&offset=` | Dokumente auflisten | `200` | Token |
| `DELETE` | `/docs/{patient_id}/{document_id}` | Dokument löschen | `204` | Token + `admin` |

## ⚠ Offen: Heißt das hier Dokument oder Anhang?

**Dieser Endpunkt widerspricht [CONTEXT.md](../CONTEXT.md). Das muss im Daily entschieden
werden, bevor es in die Präsentation geht.**

CONTEXT.md und [ADR-0001](./adr/0001-patientenakte-statt-dokumentenverwaltung.md) sagen:

> Ein **Dokument** besteht aus strukturierten Angaben, deren Felder vom **Dokumenttyp**
> abhängen, und optional aus einem **Anhang**. Ein Dokument ohne Anhang ist gültig.

Was dieser Branch baut, ist das Gegenteil:

| | CONTEXT.md | dieser Code |
| - | ---------- | ----------- |
| Dokumenttyp | bestimmt die Felder | gibt es nicht |
| Anhang | optional | **Pflicht** — ohne Datei `422` |
| Felder | je nach Typ | für alle gleich (`title`, `description`, `tags`, `source`) |

Der Code baut also einen **Anhang** und nennt ihn **Dokument**.

Zwei Wege, beide in Ordnung — aber nur einer:

1. **Wir behalten dieses Modell.** Dann wird CONTEXT.md geändert: „Dokument" ist dann eine
   Datei mit Angaben, „Dokumenttyp" fällt weg oder wird zu einem Tag. ADR-0001 bekommt
   einen Nachtrag.
2. **Wir behalten CONTEXT.md.** Dann ist dieser Endpunkt der **Anhang**-Teil eines
   Dokuments. Der Dokumenttyp und die typabhängigen Felder kommen später dazu, und die
   Pfade und Schemas hier heißen entsprechend um.

Das Wort steht in ADR-0001, in CONTEXT.md und in der Abschlusspräsentation — deshalb ist
es keine Frage, die nebenbei im Code entschieden wird.

## Wo was liegt

Drei Speicher, jeder für das, was er kann ([ADR-0002](./adr/0002-postgres-fuer-stammdaten-mongodb-fuer-dokumente.md)):

| | Wo |
| - | -- |
| Patientenstammdaten | PostgreSQL |
| Angaben zum Dokument (Titel, Tags, Größe …) | MongoDB, Collection `documents` |
| Die Datei selbst | Docker-Volume unter `UPLOAD_DIR` |

MongoDB speichert **keine Dateien** — das ist der Punkt, den ADR-0002 ausdrücklich
festhält. In der Datenbank steht nur, wo die Datei liegt.

## Das Dokument

| Feld | Typ | |
| ---- | --- | - |
| `id` | str | vom Server vergeben, 32 Hex-Zeichen |
| `patient_id` | int | zu welchem Patienten es gehört |
| `title` | str | **Pflicht**, wird getrimmt, darf nicht leer sein |
| `description` | str \| null | |
| `tags` | str[] | siehe unten |
| `source` | str \| null | woher das Dokument stammt, z. B. `"Radiologie Mitte"` |
| `created_at` | datetime | vom Server, UTC |
| `filename` | str | der ursprüngliche Dateiname — **nur als Angabe** |
| `content_type` | str \| null | was der Browser gemeldet hat |
| `size_bytes` | int | tatsächlich geschriebene Bytes |

Pflicht sind nur **`title` und die Datei**. Alles andere darf fehlen.

`filename`, `content_type` und `size_bytes` stehen nicht in der ursprünglichen
Anforderung, sind aber mit drin: Eine Dateiliste, die weder Dateinamen noch Größe zeigt,
lässt sich im Frontend nicht bedienen.

Nicht ausgeliefert werden `stored_as` (der Speicherort) und `uploaded_by`. Der Ablageort
geht von außen niemanden etwas an.

### `tags`

Kommt **kommagetrennt** herein und geht als **Liste** wieder hinaus:

```
tags=MRT, Radiologie, mrt      →      "tags": ["mrt", "radiologie"]
```

Kleingeschrieben und ohne Dubletten, damit `MRT` und `mrt` beim Filtern nicht zwei
Schlagworte sind. Die Reihenfolge der ersten Nennung bleibt erhalten — sonst flackerte die
Liste im Frontend bei jedem Laden. Höchstens 20 Tags, je höchstens 40 Zeichen.

## POST /docs/{patient_id}

**Multipart-Formular**, ein Feld `file` plus die Angaben:

```
POST /docs/42
Authorization: Bearer <token>
Content-Type: multipart/form-data

file=@befund.pdf
title=Befund MRT
description=Knie links
tags=mrt, radiologie
source=Radiologie Mitte
```

**Response `201`**

```json
{
  "id": "9f2c1ab34d5e4f7a8b0c1d2e3f4a5b6c",
  "patient_id": 42,
  "title": "Befund MRT",
  "description": "Knie links",
  "tags": ["mrt", "radiologie"],
  "source": "Radiologie Mitte",
  "filename": "befund.pdf",
  "content_type": "application/pdf",
  "size_bytes": 284913,
  "created_at": "2026-08-06T12:54:04.642189Z"
}
```

### Die 20-MB-Grenze

Über 20 MB antwortet die API mit **`413`**:

```json
{
  "status": 413,
  "message": "Die Datei ist größer als 20 MB und wurde nicht gespeichert"
}
```

Geprüft wird **beim Schreiben, nicht danach**. Erst alles einlesen und dann die Länge
messen hieße, dass eine 2-GB-Datei zuerst vollständig im Speicher landet. Stattdessen wird
in 1-MiB-Blöcken gelesen und beim Überschreiten sofort abgebrochen — es bleibt weder ein
Dokument in der Datenbank noch eine angefangene Datei auf der Platte.

Eine **leere Datei** (null Bytes) ergibt `422`.

> **Das ist die Grenze der Anwendung, nicht die des Servers.** Bis unser Code läuft, hat
> Starlette den Rumpf schon entgegengenommen. Wer eine 5-GB-Datei schickt, wird zwar
> abgewiesen, hat aber vorher Platte belegt. Sobald ein Reverse Proxy davorsteht, gehört
> dort dieselbe Grenze hin (`client_max_body_size` bei nginx). Für den Scope dieses
> Projekts genügt die Prüfung in der Anwendung.

### Der Dateiname wird nie zum Pfad

Er kommt aus dem Browser und darf alles enthalten — `../../../etc/passwd` ebenso wie einen
Patientennamen. Gespeichert wird unter `{UPLOAD_DIR}/{patient_id}/{document_id}`; der
ursprüngliche Name überlebt nur als Angabe `filename`. Von der Endung wird höchstens ein
harmloses `.pdf` übernommen.

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
  "items": [ { "id": "9f2c…", "title": "Befund MRT", "…": "…" } ],
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

## DELETE /docs/{patient_id}/{document_id}

`204`, kein Rumpf. **Angaben und Datei sind danach weg** — kein Papierkorb.

**Verlangt `admin`.** [ADR-0005](./adr/0005-rollen-admin-und-staff.md) gibt `staff`
ausdrücklich „Dokumente lesen und anlegen"; Löschen steht dort nicht, und es ist die
Aktion, die Daten unwiederbringlich entfernt. Dieselbe Linie wie beim Löschen eines
Patienten. Für `staff` kommt `403`, und das Dokument bleibt.

Die Patienten-ID im Pfad ist nicht nur Zierde: Ein Dokument lässt sich **nicht** über einen
anderen Patienten löschen — das ergibt `404`, und das Dokument bleibt heil.

Zweimaliges Löschen ist kein Serverfehler: Der zweite Aufruf antwortet mit `404`.

### Wird der Patient gelöscht, geht die Akte mit

`DELETE /patients/{id}` entfernt seither auch **alle Dokumente und Dateien** dieses
Patienten. Ohne das blieben sie liegen: über die API nicht mehr erreichbar, weil jeder
Dokument-Endpunkt den Patienten voraussetzt, und trotzdem auf der Platte.

Wie viele Dokumente dabei weggeräumt wurden, steht im Audit-Trail am Ereignis
`patient_deleted` unter `detail.documents_removed`.

## Fehler

Dieselbe Form wie überall (`status`, `message`), siehe
[patients-api.md](./patients-api.md#fehler).

| Status | Wann |
| ------ | ---- |
| `401` | kein oder ungültiger Token |
| `403` | `staff` versucht zu löschen |
| `404` | Patient oder Dokument gibt es nicht |
| `413` | Datei größer als 20 MB |
| `422` | Titel fehlt oder ist leer, Datei fehlt oder ist leer, `limit` zu groß |

## Für das Frontend

```js
const daten = new FormData();
daten.append("file", datei);            // aus <input type="file">
daten.append("title", "Befund MRT");
daten.append("tags", "mrt, radiologie"); // kommagetrennt
daten.append("source", "Radiologie Mitte");

const res = await fetch(`${base}/docs/${patientId}`, {
  method: "POST",
  headers: { Authorization: `Bearer ${token}` },  // **kein** Content-Type setzen —
  body: daten,                                    // den setzt der Browser mit boundary
});

if (res.status === 413) zeigeMeldung((await res.json()).message);
```

`Content-Type` **nicht** von Hand setzen. Der Browser trägt ihn samt `boundary` selbst ein;
wer ihn überschreibt, macht das Formular unlesbar.

Die Größe lässt sich vorab im Browser prüfen (`datei.size > 20 * 1024 * 1024`) — das spart
den Upload. Es ist Bedienkomfort, keine Absicherung: Durchgesetzt wird im Backend.

## Im Audit-Trail

Hochladen und Löschen werden festgehalten
([logging-monitoring.md](./logging-monitoring.md)) — als `document_uploaded` und
`document_deleted`, mit `document:<id>` und `patient:<id>`.

**Weder Dateiname noch Titel landen im Trail.** Beide heißen in der Praxis gern
„Mueller_Befund.pdf" und wären damit genau die Patientenangabe, die dort nicht hingehört.
Festgehalten werden Größe und Typ; die sagen genug, um einen Vorfall einzuordnen.

## Offene Punkte

- **Dokument oder Anhang** — der Widerspruch zu CONTEXT.md, siehe
  [oben](#-offen-heißt-das-hier-dokument-oder-anhang). **Fürs nächste Daily.**
- **Es gibt keinen Download.** Die Anforderung nennt Hochladen, Auflisten und Löschen — die
  Bytes sind damit vorerst nur ablegbar, nicht wieder abrufbar. Ein
  `GET /docs/{patient_id}/{document_id}/file` wäre der nächste Schritt und ist klein; er
  muss nur dieselbe Prüfung fahren (Token, Patient, Zugehörigkeit) und den Speicherort
  weiterhin geheim halten.
- **Der Pfad `/docs` gehört auch der Swagger-Oberfläche.** FastAPI liefert sie unter dem
  exakten Pfad `/docs` aus, unsere Routen beginnen erst darunter (`/docs/42`) — beides
  läuft nebeneinander, und ein Test wacht darüber. Verwechslungsfrei ist es trotzdem
  nicht, und der übrige Bestand heißt `/patients`. **`/patients/{id}/documents` wäre der
  saubere Zug** und würde nebenbei ausdrücken, dass ein Dokument ohne Patient nicht
  existiert. Gehört ins Daily.
- **Kein Virenscan, keine Typprüfung.** Hochgeladen werden darf alles. In einer echten
  Praxis wäre beides Pflicht.
- **Keine Vorschau, keine Größenbeschränkung pro Patient.**

## Tests

[`backend/tests/test_documents_api.py`](../backend/tests/test_documents_api.py), gegliedert
nach Endpunkt, dazu eigene Blöcke für die Größenprüfung und die Ablage auf der Platte. Sie
laufen gegen den Speicher-Store und einen temporären Ordner — kein MongoDB, kein Docker.

Der wichtigste Test ist `test_der_dateiname_des_aufrufers_wird_nie_zum_pfad`.
