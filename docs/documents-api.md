# Dokumente — API-Vertrag

> **Zweck:** Dokumente in der Akte eines Patienten anlegen, auflisten und löschen. Diese
> Datei ist die verbindliche Form. Ändert sich hier etwas, wird es hier geändert und im
> Daily gesagt.
>
> Patienten-API: [patients-api.md](./patients-api.md).
> Auth-Vertrag: [auth-api.md](./auth-api.md).
> Warum MongoDB: [ADR-0002](./adr/0002-postgres-fuer-stammdaten-mongodb-fuer-dokumente.md).

Basis-URL lokal: `http://localhost:8000`

## Kurzfassung

- **Jeder Endpunkt verlangt einen gültigen Token.** `DELETE` verlangt zusätzlich `admin`.
- Angelegt wird **multipart**, nicht JSON — anders reisen Anhänge nicht.
- **Anhänge sind optional und dürfen mehrere sein.** Ein Befund aus drei gescannten Seiten
  ist **ein** Dokument mit drei Anhängen.
- **Höchstens 20 MB** je Anhang, höchstens 20 Anhänge. Darüber `413` bzw. `422`.
- Ein Dokument gehört immer zu genau einem Patienten. Gibt es den nicht, kommt `404`.

| Methode | Pfad | Zweck | Erfolg | Verlangt |
| ------- | ---- | ----- | ------ | -------- |
| `POST` | `/patients/{patient_id}/documents` | Dokument anlegen | `201` | Token |
| `GET` | `/patients/{patient_id}/documents?q=&limit=&offset=` | Dokumente auflisten | `200` | Token |
| `GET` | `…/documents/{document_id}/attachments/{attachment_id}` | Anhang abrufen | `200` | Token |
| `DELETE` | `…/documents/{document_id}` | Dokument löschen | `204` | Token + `admin` |

## Namensgebung

Wie in [patients-api.md](./patients-api.md#namensgebung): **Pfad, Query-Parameter,
Formularfelder und JSON-Keys sind englisch.** Deutsch sind Kommentare, diese Doku und die
Oberfläche im Frontend.

Für die Fachbegriffe gilt [CONTEXT.md](../CONTEXT.md), und zwar wörtlich. Die Spalte
**Nicht sagen** meint die *deutsche* Prosa — Kommentare, diese Doku, die Oberfläche:

| Begriff | Was gemeint ist | Nicht sagen |
| ------- | --------------- | ----------- |
| **Dokument** | ein Eintrag in der Akte — Angaben plus beliebig viele Anhänge | Datei, Upload, Eintrag |
| **Dokumenttyp** | die Art des Dokuments; ein Schlagwort zum Filtern | Kategorie, Art, Klasse |
| **Anhang** | die angehängte Datei zu einem Dokument | Datei, Attachment, Upload |

Zwei Ausnahmen, und nur diese zwei:

**Englische Bezeichner sind keine deutsche Prosa.** Der JSON-Key heißt `attachments` und die
Klasse `Attachment`, weil oben steht, dass JSON-Keys englisch sind — `attachment` *ist* die
englische Übersetzung von **Anhang** und damit richtig. Verboten ist „Attachment" im
deutschen Satz („das Attachment wird gespeichert"), nicht der Bezeichner. Dasselbe gilt für
`UPLOAD_DIR` und `MAX_UPLOAD_BYTES`: Namen der Ablage, nicht der Fachlichkeit.

**`backend/app/modules/documents/storage.py` redet von *Dateien*.** Dort geht es wirklich um
Bytes auf einem Dateisystem — um Blöcke, Endungen und Pfade —, nicht um den fachlichen
Begriff. Überall sonst im Code heißt er **Anhang**.

## Das Modell

Ein **Dokument** besteht aus beschreibenden Angaben — `document_type`, `title`,
`description`, `tags` — und **beliebig vielen Anhängen**. Für jedes Dokument gelten
dieselben Felder, unabhängig vom Typ.

**`source` gehört zum Anhang, nicht zum Dokument.** Die Herkunft beschreibt, woher *dieses
Blatt* kam; ein Dokument darf Anhänge aus verschiedenen Quellen bündeln — den Scan aus der
Radiologie und die Notiz aus der eigenen Praxis.

### Warum es keine typabhängigen Felder gibt

Ein Dokument hatte zwischenzeitlich ein Feld `fields`: einen freien Satz Schlüssel/Wert,
den jeder Dokumenttyp nach Belieben füllen konnte. **Das ist wieder entfernt worden**, und
zwar aus einem Grund, der in einer Akte schwerer wiegt als die verlorene Flexibilität:

> Ohne eine **Definition je Dokumenttyp** entstehen redundante Daten. Der eine schreibt
> `hb`, der nächste `Hb`, der dritte `haemoglobin` — drei Schlüssel für denselben Wert.
> Eine Auswertung über „alle Hämoglobinwerte dieses Patienten" findet dann ein Drittel.
> Dasselbe für Einheiten: `g/dl` neben `g/dL` neben `gramm pro deziliter`.
>
> Ein freies Objekt kann außerdem nichts erzwingen und nichts prüfen: kein Pflichtfeld,
> kein Zahlenbereich, keine Einheit, kein Tippfehler-Alarm. Es sieht aus wie Struktur und
> ist keine.

**Vertagt, nicht verworfen.** Typabhängige Felder kommen, sobald je Dokumenttyp festliegt,
welche Felder es gibt — Name, Datentyp, Einheit, Pflicht ja/nein. Dann validiert das
Backend gegen diesen Katalog, und das Frontend baut das Eingabeformular daraus, statt ein
leeres JSON-Feld anzubieten. Bis dahin gilt: **keine Felder statt beliebiger Felder.**

Was das braucht, in dieser Reihenfolge:

1. Fachliche Festlegung je Typ — welche Felder trägt ein `laborwert`, welche ein `befund`?
2. Eine Ablage für diesen Katalog (Collection oder Datei) und ein Endpunkt, der ihn ausgibt.
3. Prüfung beim Anlegen gegen den Katalog des angegebenen Typs.

Schritt 1 ist fachliche Arbeit und gehört nicht ins Backend allein.

> ### ⚠ Das trifft ADR-0002 und gehört ins Daily
>
> [ADR-0002](./adr/0002-postgres-fuer-stammdaten-mongodb-fuer-dokumente.md) begründet die
> zweite Datenbank mit der **Heterogenität der Angaben**: „Ein Laborwert hat völlig andere
> Felder als ein Arztbrief." Solange es keine typabhängigen Felder gibt, stimmt das nicht —
> alle Dokumente sind gleich aufgebaut, und die Anhänge sind eine gewöhnliche Liste. **Was
> heute in MongoDB liegt, könnte PostgreSQL genauso.**
>
> Das ist kein Grund, sofort umzubauen: MongoDB läuft, ist eingerichtet, und der Katalog
> oben bringt die Heterogenität zurück. Aber ADR-0002 nennt sich selbst „ein zentraler
> Punkt der Abschlusspräsentation" — und dort wird jemand genau das fragen. Die ehrliche
> Antwort ist der Fahrplan oben, nicht die alte Begründung.

## Wo was liegt

Drei Speicher, jeder für das, was er kann:

| | Wo |
| - | -- |
| Patientenstammdaten | PostgreSQL |
| Angaben zum Dokument (Typ, Titel, Tags, Anhang-Angaben …) | MongoDB, Collection `documents` |
| Die Bytes der Anhänge | Docker-Volume unter `UPLOAD_DIR` |

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
| `attachments` | object[] | die Anhänge — **nie `null`**, höchstens leer |
| `created_at` | datetime | vom Server, UTC |

Jeder Eintrag in **`attachments`**:

| Feld | Typ | |
| ---- | --- | - |
| `id` | str | vom Server vergeben |
| `filename` | str \| null | der ursprüngliche Dateiname — **nur als Angabe** |
| `content_type` | str \| null | was der Browser gemeldet hat |
| `size_bytes` | int | tatsächlich geschriebene Bytes |
| `source` | str \| null | woher **dieses Blatt** stammt, z. B. `"Radiologie Mitte"` |
| `url` | str | Adresse zum **Ansehen** (Vorschau) |
| `download_url` | str | Adresse zum **Herunterladen** |

Pflicht sind nur **`document_type` und `title`**. Alles andere darf fehlen — auch die
Anhänge.

`attachments` ist **immer eine Liste**, nie `null`. Ein Dokument ohne Anhang hat `[]`;
damit lässt sich im Frontend ohne Fallprüfung darüber laufen.

`filename` ist `null`, wenn der Aufrufer keinen Namen mitgeschickt hat. Der Server denkt
sich **keinen** aus: Ein zusammengebautes `<id>.bin` sähe im Frontend aus wie ein echter
Name des Benutzers.

Nicht ausgeliefert werden `stored_as` (der Speicherort) und `created_by`. Der Ablageort
geht von außen niemanden etwas an — an seine Stelle treten `url` und `download_url`.

### `document_type`

Wird **getrimmt und kleingeschrieben** — sonst wären `Befund` und `befund` zwei Typen und
eine Liste „alle Befunde" fände nur die Hälfte.

Geprüft wird **nicht** gegen eine feste Liste. CONTEXT.md verlangt ausdrücklich: „Neue
Dokumenttypen sollen ohne Schemaänderung möglich sein." Ein neuer Typ kostet damit keine
Codeänderung.

Üblich sind — als Verabredung, nicht als Zwang (siehe
[sprint-1-plan.md](./sprint-1-plan.md)):

`befund` · `arztbrief` · `laborwert` · `sonstiges`

### `tags`

Kommt **kommagetrennt** herein und geht als **Liste** wieder hinaus:

```
tags=MRT, Radiologie, mrt      →      "tags": ["mrt", "radiologie"]
```

Kleingeschrieben und ohne Dubletten, damit `MRT` und `mrt` beim Filtern nicht zwei
Schlagworte sind. Die Reihenfolge der ersten Nennung bleibt erhalten — sonst flackerte die
Liste im Frontend bei jedem Laden. Höchstens 20 Tags, je höchstens 40 Zeichen.

## POST /patients/{patient_id}/documents

**Multipart-Formular**, die Angaben plus beliebig viele Felder `files`:

```
POST /patients/42/documents
Authorization: Bearer <token>
Content-Type: multipart/form-data

document_type=befund
title=Befund MRT
description=Knie links
tags=mrt, radiologie
files=@seite1.pdf                     ← beliebig oft, auch gar nicht
files=@seite2.pdf
source=Radiologie Mitte               ← je Anhang, oder einmal für alle
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
  "attachments": [
    {
      "id": "3fb1ce719d244a10bb5373163be8c1e7",
      "filename": "seite1.pdf",
      "content_type": "application/pdf",
      "size_bytes": 284913,
      "source": "Radiologie Mitte",
      "url": "/patients/42/documents/9f2c1ab34d5e4f7a8b0c1d2e3f4a5b6c/attachments/3fb1ce719d244a10bb5373163be8c1e7",
      "download_url": "/patients/42/documents/9f2c1ab34d5e4f7a8b0c1d2e3f4a5b6c/attachments/3fb1ce719d244a10bb5373163be8c1e7?download=true"
    }
  ],
  "created_at": "2026-08-06T12:54:04.642189Z"
}
```

### Die Herkunft je Anhang

`source` wird den Anhängen **der Reihe nach** zugeordnet:

| Anhänge | `source` | Ergebnis |
| ------- | -------- | -------- |
| 3 | einmal `"Radiologie Mitte"` | gilt für alle drei |
| 2 | `"Radiologie Mitte"`, `"Eigene Praxis"` | je Anhang einer |
| 3 | zwei Angaben | der dritte bleibt ohne — kein Fehler |
| 2 | gar keine | beide ohne — `source` ist optional |

### Ohne Anhang

Ein Laborwert braucht keinen Scan. **Das Feld `files` einfach weglassen** — dann entsteht
ein Dokument mit `"attachments": []`, und die Platte wird gar nicht erst angefasst.

> **Weglassen, nicht leer schicken.** Wird ein Anhang mitgeschickt, muss etwas drin sein:
> eine Datei mit null Bytes ist ein Versehen und ergibt `422`. Das Frontend hängt das Feld
> also nur an, wenn der Benutzer wirklich etwas ausgewählt hat.
>
> **Achtung, Nebenwirkung:** Da `source` am Anhang hängt, hat ein Dokument **ohne** Anhang
> auch keine Herkunft mehr. In den Testdaten hat das sechs Laborwerte ihre Quelle gekostet
> („Labor Berlin Mitte"). Wer die Herkunft auch ohne Anhang braucht, muss sie zusätzlich
> ans Dokument hängen — das wäre eine Änderung am Vertrag.

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
Patientennamen. Gespeichert wird unter
`{UPLOAD_DIR}/{patient_id}/{document_id}/{attachment_id}`; der ursprüngliche Name überlebt
nur als Angabe `filename`. Von der Endung wird höchstens ein harmloses `.pdf` übernommen.

Ein Ordner je Dokument, darin eine Datei je Anhang — seit ein Dokument mehrere tragen kann,
hielte ein gemeinsamer Ordner sie nur über den Dateinamen auseinander, und der kommt vom
Aufrufer.

## GET /patients/{patient_id}/documents

```
GET /patients/42/documents?q=mrt&limit=100&offset=0
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

> `q` durchsucht **Titel und Beschreibung**, sonst nichts — insbesondere keine Dateinamen
> der Anhänge. Die tragen in der Praxis oft Patientennamen; eine Suche darüber wäre eine
> eigene Entscheidung. Siehe [Offene Punkte](#offene-punkte).

## GET …/documents/{document_id}/attachments/{attachment_id}

**So kommt das Frontend an die Bytes eines Anhangs.** Die Adresse steht fertig in jeder
Dokumentantwort — sie muss nicht selbst zusammengesetzt werden:

| Feld | Antwort trägt | Wofür |
| ---- | ------------- | ----- |
| `url` | `Content-Disposition: inline` | Vorschau — `<img>`, `<iframe>`, Bild im Dialog |
| `download_url` | `Content-Disposition: attachment` | Speichern-Dialog des Browsers |

Beides ist **dieselbe Route**; `download_url` hängt nur `?download=true` an.

```
GET /patients/42/documents/9f2c…/attachments/3fb1…            → Vorschau
GET /patients/42/documents/9f2c…/attachments/3fb1…?download=true   → Download
Authorization: Bearer <token>
```

Die Antwort trägt `Content-Type` und den ursprünglichen Dateinamen, damit der Browser weiß,
was er anzeigen soll und wie die Datei beim Speichern heißt.

**Alle drei Kennungen müssen zusammenpassen.** Wer die Kennung eines fremden Anhangs errät,
bekommt ihn nicht über den eigenen Patienten: Passt eine nicht, ist die Antwort `404` —
dieselbe wie für „gibt es nicht", damit sie nicht verrät, welcher Teil gestimmt hätte.

Fehlt die Datei auf der Platte, obwohl die Angaben sie nennen, kommt ebenfalls `404`; im
Server-Log steht dann ein `ERROR` mit den Kennungen.

> **Der Token muss mit.** Der Endpunkt ist geschützt wie jeder andere — ein `<img src>` im
> Browser schickt keinen `Authorization`-Header. Das Frontend holt den Anhang deshalb per
> `fetch` und macht daraus eine Objekt-URL, siehe [unten](#für-das-frontend).

## DELETE …/documents/{document_id}

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
| `422` | `document_type` oder `title` fehlt/ist leer, ein mitgeschickter Anhang ist leer, mehr als 20 Anhänge, `limit` zu groß |

## Für das Frontend

### Anlegen

```js
const form = new FormData();
form.append("document_type", "befund");
form.append("title", "Befund MRT");
form.append("tags", "mrt, radiologie");         // kommagetrennt

// Anhaenge sind optional und duerfen mehrere sein. Das Feld nur anhaengen,
// wenn wirklich Dateien ausgewaehlt wurden — ein leeres waere ein Fehler,
// kein "kein Anhang".
for (const file of files) form.append("files", file);   // aus <input type="file" multiple>

// Einmal fuer alle Anhaenge — oder einmal je Anhang, in derselben Reihenfolge.
form.append("source", "Radiologie Mitte");

const res = await fetch(`${base}/patients/${patientId}/documents`, {
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

### Anhang anzeigen oder herunterladen

Der Endpunkt ist geschützt, und ein `<img src>` schickt keinen `Authorization`-Header.
Deshalb wird der Anhang per `fetch` geholt und in eine Objekt-URL verwandelt:

```js
async function anhangOeffnen(anhang) {
  const res = await fetch(base + anhang.url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) return showMessage((await res.json()).message);

  const objektUrl = URL.createObjectURL(await res.blob());
  // <img src={objektUrl}> oder <iframe src={objektUrl}> — je nach content_type.
  // Wenn die Vorschau zu ist: URL.revokeObjectURL(objektUrl), sonst bleibt der
  // Blob im Speicher liegen.
  return objektUrl;
}
```

Zum **Herunterladen** dasselbe mit `anhang.download_url` und einem `<a download>` auf die
Objekt-URL; `filename` aus der Antwort ist der Name, den der Benutzer erwartet.

Ob Vorschau oder nur ein Link, entscheidet `content_type`: `image/*` und
`application/pdf` lassen sich anzeigen, alles andere bietet man zum Speichern an.

### Beim Anzeigen der Liste

`attachments` ist **immer eine Liste** — bei einem Dokument ohne Anhang eben `[]`. Kein
`null`-Fall, keine Sonderbehandlung. Ein Dokument ohne Anhang ist kein Fehlerfall, sondern
ein gültiges Dokument.

## Im Audit-Trail

Anlegen und Löschen werden festgehalten
([logging-monitoring.md](./logging-monitoring.md)) — als `document_created` und
`document_deleted`, mit `document:<id>` und `patient:<id>`.

`document_created` und nicht `document_uploaded`: Ein Dokument entsteht auch ohne Anhang,
hochgeladen wird dabei nichts.

**Weder Dateiname noch Titel landen im Trail.** Beide heißen in der Praxis gern
„Mueller_Befund.pdf" und wären damit genau die Patientenangabe, die dort nicht hingehört.
Aus demselben Grund steht auch `source` nicht drin — Freitext, in dem in der Praxis alles landet.
Festgehalten werden Dokumenttyp, die **Anzahl** der Anhänge und ihre Gesamtgröße; die sagen
genug, um einen Vorfall einzuordnen, und der Dokumenttyp ist eine feste Fachkategorie, die
nichts über den Patienten verrät.

## Offene Punkte

- **Typabhängige Felder fehlen noch** — und mit ihnen die Begründung, die ADR-0002 für
  MongoDB gibt. Beides hängt am selben Fahrplan: erst ein Feldkatalog je Dokumenttyp,
  siehe [Warum es keine typabhängigen Felder gibt](#warum-es-keine-typabhängigen-felder-gibt).
  **Fürs nächste Daily.**
- **Ein Dokument ohne Anhang hat keine Herkunft mehr.** `source` hängt am Anhang. In den
  Testdaten hat das sechs Laborwerte ihre Quelle gekostet.
- **Anhänge lassen sich nur beim Anlegen mitgeben.** Es gibt keinen Endpunkt, der einem
  bestehenden Dokument einen Anhang hinzufügt oder einen einzelnen entfernt — beides wäre
  klein (`POST`/`DELETE` unter `…/attachments`), war aber nicht gefordert.
- **`q` durchsucht die Anhänge nicht**, nur Titel und Beschreibung. Dateinamen wären
  denkbar; sie tragen in der Praxis allerdings oft Patientennamen.
- **Es gibt keine Liste erlaubter Dokumenttypen.** Das ist Absicht (CONTEXT.md: neue Typen
  ohne Schemaänderung), heißt aber auch: Ein Tippfehler legt einen neuen Typ an. Sobald das
  Frontend eine Auswahl anbietet, ist das praktisch entschärft.
- **Kein Virenscan, keine Typprüfung.** Angehängt werden darf alles. In einer echten
  Praxis wäre beides Pflicht.
- **Keine Größenbeschränkung pro Patient und keine Serverseiten-Vorschau.** Das Anzeigen
  übernimmt der Browser; eine Miniaturansicht müsste das Backend erzeugen.

## Tests

[`backend/tests/test_documents_api.py`](../backend/tests/test_documents_api.py), gegliedert
nach Endpunkt, dazu eigene Blöcke für Dokumenttyp, typabhängige Angaben, Dokumente ohne
Anhang, die Größenprüfung und die Ablage auf der Platte. Sie laufen gegen den
Speicher-Store und einen temporären Ordner — kein MongoDB, kein Docker.

Der wichtigste Test ist `test_der_dateiname_des_aufrufers_wird_nie_zum_pfad`.

## Testdaten

17 frei erfundene Dokumente liegen als JSON in
[`backend/testdata/documents.json`](../backend/testdata/documents.json), verteilt auf die
ersten sechs Testpatienten. Alle vier üblichen Dokumenttypen kommen vor, dazu Dokumente
**mit einem, mit mehreren und ohne** Anhang — und Patienten ganz ohne Dokumente, damit der
Leerzustand der Liste genauso zu sehen ist wie eine volle Akte.

```bash
python -m app.seed          # legt Patienten und Dokumente an
```

Mehrfach ausführbar: Die Dokumente haben feste Kennungen (`5eed…`), ein zweiter Lauf
erkennt sie wieder.

> **`patient_id` muss zu den Kennungen aus Postgres passen.** In der Datei steht die `id`
> direkt als Zahl. Das geht auf, weil die Patienten in der Reihenfolge von `patients.json`
> angelegt werden und Postgres fortlaufend ab 1 vergibt — Datensatz eins wird `1`,
> Datensatz zwei wird `2`. **Das gilt nur für eine leere Tabelle.** Wer vorher von Hand
> Patienten angelegt hat, bekommt andere Kennungen, und dann hängen die Dokumente an den
> falschen Leuten. Der verlässliche Weg ist ein Lauf nach `docker compose down -v`.
>
> Dokumente, deren Patient es nicht gibt — etwa nach `--patients 3` —, werden übersprungen
> und in der Ausgabe gezählt. Das ist kein Fehler.

Die Anhänge sind Platzhalter: In der Datei steht, wie die Datei hieß und was der Browser
gemeldet hätte, die Bytes selbst schreibt der Seed als kurzen Text. Die Größe ist damit
echt, und abrufbar sind sie wie alle anderen.
