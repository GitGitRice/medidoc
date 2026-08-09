---
status: accepted
---

# MongoDB für den Audit-Trail, kein Redis

Anmeldeversuche und auffällige Zugriffe sollen festgehalten und auswertbar sein. Zur Wahl
standen **Redis** und **MongoDB**. Wir nehmen **MongoDB** — und zwar allein, ohne Redis
daneben.

## Gemessen, nicht geraten

Beide Kandidaten wurden mit den drei Zugriffsmustern gemessen, die wir wirklich brauchen
(je 3000 Operationen, Docker auf einer Maschine, `p50`):

| Zugriffsmuster | Redis | MongoDB |
| -------------- | ----- | ------- |
| Zähler hochsetzen (`INCR+EXPIRE` / `findOneAndUpdate $inc`) | **0,064 ms** | 0,112 ms |
| Ereignis anhängen (`XADD` / `insert_one`) | **0,062 ms** | 0,100 ms |
| Zeitfenster auswerten (`GET` / `count` über Index) | **0,055 ms** | 0,124 ms |

**Redis ist rund doppelt so schnell.** Wir nehmen trotzdem MongoDB, weil der Faktor zwei
hier nichts entscheidet: Beide liegen weit unter einer Zehntel-Millisekunde, und eine
Arztpraxis mit einer Handvoll Personal erzeugt keine Last, bei der das messbar wird. Der
Unterschied, der zählt, ist ein anderer.

## Was den Ausschlag gibt

**Der Trail muss Fragen beantworten, nicht nur zählen.** „Wie oft ist Anna letzte Woche
gescheitert?", „Wer hat Patient 42 gelöscht?" — das sind Abfragen über Felder und
Zeiträume. In MongoDB ist das eine gewöhnliche Query über einen Index. In Redis müsste man
dafür eine Datenstruktur je Frage anlegen und pflegen; Redis würde zur Datenbank umgebaut,
für die es nicht gedacht ist.

**Der Trail muss den Neustart überleben.** Ein Protokoll, das beim Neustart verschwindet,
ist im Zweifel genau dann weg, wenn man es braucht. Redis kann persistieren, aber
Haltbarkeit ist dort eine Konfigurationsfrage; in MongoDB ist sie der Normalfall.

**MongoDB ist ohnehin gesetzt.** [ADR-0002](./0002-postgres-fuer-stammdaten-mongodb-fuer-dokumente.md)
sieht MongoDB für die Dokumente in Sprint 2 vor. Der Trail nutzt denselben Service, nur
eine eigene Collection (`audit_events`). Redis wäre ein **dritter** Datenspeicher für ein
Problem, das der zweite mit erledigt — und jeder zusätzliche Dienst ist ein Dienst, den
jemand starten, verstehen und in der Präsentation erklären muss.

**Aufräumen erledigt die Datenbank.** Ein TTL-Index auf `ts` löscht Einträge nach
`AUDIT_RETENTION_DAYS` von selbst. Niemand muss putzen, und niemand vergisst es.

## Wann Redis doch richtig wäre

Wenn wir **blockieren** würden statt nur zu erkennen. Ein Rate Limit muss vor jeder
Anfrage einen Zähler lesen und schreiben, und dann gehört dieser Zähler in den Speicher und
nicht auf eine Platte. Wir blockieren bewusst nicht (siehe
[docs/logging-monitoring.md](../logging-monitoring.md)), also entsteht dieser heiße Pfad
gar nicht. Ändert sich das, ist Redis die richtige Antwort — die Messwerte oben stehen
dann bereit.

## Konsequenzen

- Ein `mongo`-Service in Docker Compose, mit eigenem Volume. Ab Sprint 2 liegen die
  Dokumente daneben, in einer anderen Collection.
- **Die Anwendung startet auch ohne MongoDB.** Ist `MONGO_URL` leer oder Mongo nicht
  erreichbar, läuft der Trail im Prozessspeicher und ist nach dem Neustart weg. Das ist der
  Modus, in dem die Tests und die CI laufen — sie brauchen keinen Datenbank-Service.
- **Ein Fehler beim Protokollieren kippt nie einen Request.** Zugesichert in
  `audit.service.record`, nicht in einer einzelnen Store-Ausführung, damit die Zusicherung
  auch für eine künftige gilt.
- Der Trail ist über die API **nur lesbar** und nur für `admin`. Ein Audit-Trail, den man
  löschen kann, ist keiner.
- Kein Werkzeug wie Prometheus oder Grafana. Für die Vorführung reichen `docker compose
  logs` und `GET /monitoring/ereignisse`; alles andere wäre Infrastruktur ohne Nutzen im
  Scope.

## Nachtrag Sprint 2 — „startet auch ohne MongoDB" gilt nur noch für den Trail

Als diese Entscheidung fiel, hing an MongoDB nur der Audit-Trail. Seit den Dokumenten
([documents-api.md](../documents-api.md)) hängt dort auch die Akte jedes Patienten. Die
Zusicherung oben wird deshalb geteilt:

- **Der Audit-Trail bleibt wie beschrieben.** Ohne `MONGO_URL` läuft er im Prozessspeicher
  und ist nach dem Neustart weg. Ein verlorener Protokolleintrag ist ärgerlich, mehr nicht
  — und es ist der Modus, in dem die Tests und die CI laufen.
- **Die Dokumente nicht.** Ohne `MONGO_URL` antworten die Dokument-Endpunkte mit `500`,
  statt in den Speicher auszuweichen. Ein Anlegen, das `201` meldet, den Anhang wirklich
  auf die Platte schreibt und dessen Dokument den Neustart nicht überlebt, ist schlimmer
  als eine Fehlermeldung: Ein verlorener Befund fällt niemandem auf.
- **Compose wartet deshalb auf `service_healthy` statt `service_started`.** „Der Container
  läuft" genügt nicht mehr, wenn die erste Anfrage schon Angaben schreiben will.

Die Anwendung als Ganzes startet weiterhin ohne MongoDB — nur die Dokument-Endpunkte
antworten dann mit einem Fehler statt mit einer Lüge.
