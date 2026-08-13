# Logging und Monitoring

> **Zweck:** Nachvollziehen, was im Backend passiert — und merken, wenn jemand an Türen
> rüttelt. Die Entscheidung für MongoDB steht mit Messwerten in
> [ADR-0007](./adr/0007-mongodb-fuer-audit-und-monitoring.md).

## Drei Schichten

Sie beantworten drei verschiedene Fragen und werden deshalb nicht vermischt.

| Schicht | Frage | Wo | Haltbarkeit |
| ------- | ----- | -- | ----------- |
| **Log** | Was tut der Server gerade? | stdout, `app/core/logging.py` | flüchtig |
| **Audit-Trail** | Wer hat wann was getan? | MongoDB, `app/modules/audit/` | 30 Tage (TTL) |
| **Erkennung** | Rüttelt jemand an einer Tür? | zählt über den Trail | Treffer landen im Trail |

Der häufigste Fehler wäre, alles in eine Schicht zu kippen: Ein Log, in dem auch der
Audit-Trail steht, ist nach dem Neustart weg. Ein Trail, in dem auch jeder Seitenaufruf
steht, ist nicht mehr auswertbar.

## 1. Log — eine Zeile pro Anfrage

Erzeugt von `RequestContextMiddleware` (`app/core/middleware.py`). Weil sie als Middleware
hängt, gilt sie für **jeden** Endpunkt — auch für einen, den morgen jemand dazuschreibt.

```
2026-08-05 10:45:36 WARNING medidoc.request  POST /auth/login -> 401
  request_id=5ec19e6f method=POST path=/auth/login status=401 duration_ms=167.7 user_id=None ip=172.18.0.1
```

| Feld | |
| ---- | - |
| `request_id` | verbindet Logzeile, Audit-Eintrag und Antwort-Header `X-Request-ID` |
| `duration_ms` | wie lange die Anfrage gebraucht hat |
| `user_id` | wer, sofern der Token gültig war |
| `status` | `5xx` → ERROR, `4xx` → WARNING, sonst INFO |

`LOG_JSON=true` schaltet auf eine JSON-Zeile pro Ereignis um — so läuft es im Container,
damit ein Log-Sammler es lesen kann. Lokal ist `false` angenehmer.

`GET /health` wird nicht geloggt: Docker fragt es im Sekundentakt, es machte sonst das
halbe Log aus.

### Die Anfrage-Kennung

Jede Antwort trägt `X-Request-ID`. Meldet jemand „bei mir kam ein Fehler", genügt diese
Kennung, um die passende Zeile im Server-Log und den Eintrag im Trail zu finden. Sie wird
in der äußersten Middleware vergeben und über einen `ContextVar` weitergereicht — kein
Durchreichen als Parameter durch jede Funktion.

## 2. Audit-Trail — wer hat was getan

Kein zweites Anwendungslog. Hier landet nur, was eine **Sicherheitsfrage** beantwortet.

| Ereignis | Wann | Schwere |
| -------- | ---- | ------- |
| `login_succeeded` | Anmeldung geglückt | info |
| `login_failed` | Anmeldung gescheitert, **mit der versuchten E-Mail** | warning |
| `token_rejected` | `401` an einem geschützten Endpunkt | warning |
| `forbidden` | `403` — angemeldet, aber Rolle reicht nicht | warning |
| `not_found` | `404` — einzeln harmlos, gehäuft eine Enumeration | warning |
| `patient_created` / `patient_updated` / `patient_deleted` | schreibender Zugriff | info |
| `document_created` / `document_deleted` | Dokument angelegt oder gelöscht — **ohne** Dateiname, Titel und `fields` | info |
| `suspicious` | eine Regel hat angeschlagen | warning |

**Lesende Zugriffe auf Patienten stehen nicht drin.** Die Übersicht wird den ganzen Tag
aufgerufen; jeder Aufruf im Trail machte ihn unlesbar. Wer *jeden* Zugriff auf eine Akte
protokollieren will — in einer echten Praxis wäre das eine berechtigte Forderung —, muss
das bewusst einschalten und die Datenmenge einplanen.

### Warum der Login sein Ereignis selbst schreibt

Fast alles leitet die Middleware aus dem Statuscode ab. Beim Fehlversuch geht das nicht:
Die Antwort verrät bewusst nicht, ob E-Mail oder Passwort falsch war (siehe
[auth-api.md](./auth-api.md)) — dieselbe `401` also für beides. Welches Konto gemeint war,
weiß nur der Endpunkt. Ohne diese Angabe wüsste man nur, dass irgendwer gescheitert ist,
und könnte einen Angriff auf ein bestimmtes Konto nicht erkennen.

Die E-Mail wird normalisiert festgehalten. Sonst liefe jemand mit wechselnder Schreibweise
unter jeder Schwelle durch.

### Was niemals hineingehört

**Keine Passwörter, keine Token, keine Hashes.** `app/core/logging.py` ersetzt die Werte
solcher Felder durch `***`, rekursiv, egal wer sie mitgibt.

**Keine Patientendaten.** Ein Ereignis nennt `patient:42` — nie einen Namen, ein
Geburtsdatum oder eine Versichertennummer. Beim Ändern wird festgehalten, *welche Felder*
angefasst wurden, nicht womit sie gefüllt wurden:

```json
{
  "ts": "2026-08-05T10:45:36.291Z",
  "event": "patient_updated",
  "severity": "info",
  "request_id": "c6a8306ad2f14e1b…",
  "user_id": 1,
  "ip": "172.18.0.1",
  "method": "PATCH",
  "path": "/patients/42",
  "status": 200,
  "target": "patient:42",
  "detail": { "fields": ["city", "phone"] }
}
```

Der Grund ist nicht Förmlichkeit: Der Trail liegt dauerhaft in einer eigenen Datenbank und
ist damit genau die Stelle, an der eine unbedachte Zeile am längsten überlebt. Wer wissen
will, wer Patient 42 ist, hat dafür die Patiententabelle — und einen Grund.

## 3. Erkennung — nur erkennen, nie blockieren

Nach jedem Ereignis wird sofort gezählt: „Kam das in den letzten `ABUSE_WINDOW_MINUTES`
öfter als erlaubt für denselben Wert vor?" Kein Hintergrundlauf — die Warnung steht in
derselben Sekunde im Log wie das auslösende Ereignis.

| Regel | Zählt | Je | Vorgabe |
| ----- | ----- | -- | ------- |
| `brute_force_email` | `login_failed` | E-Mail | 5 |
| `brute_force_ip` | `login_failed` | IP | 10 |
| `token_probing` | `token_rejected` | IP | 10 |
| `privilege_probing` | `forbidden` | Benutzer | 3 |
| `id_enumeration` | `not_found` | Benutzer | 20 |

`id_enumeration` ist die Regel, die bei Patientendaten wirklich zählt: Jemand ruft
`/patients/1`, `/patients/2`, `/patients/3` … auf, um herauszufinden, welche Akten es
gibt. Ein einzelnes `404` ist nichts, zwanzig sind ein Muster.

Die Warnung kommt **einmal je Überschreitung**, nicht bei jedem weiteren Versuch — sonst
liefe der Trail mit Wiederholungen desselben Befunds voll.

> ### Es wird nie blockiert
>
> Diese Schicht schreibt und warnt. Sie lehnt **keinen** Request ab: kein `429`, keine
> Kontosperre. Ein Fehlalarm kostet damit eine Logzeile und nicht die Vorführung — und
> niemand kann sich selbst aussperren.
>
> Das ist eine bewusste Entscheidung für Sprint 1, kein Versehen. Ein echtes Rate Limit ist
> die naheliegende Erweiterung; wer sie baut, hat mit dem Trail die Zahlen, um die Schwelle
> zu begründen, statt sie zu raten. Dann gehört der Zähler allerdings nach Redis, siehe
> [ADR-0007](./adr/0007-mongodb-fuer-audit-und-monitoring.md#wann-redis-doch-richtig-wäre).

## Hineinsehen

### Im Log

```bash
docker compose logs -f fastapi
```

### Über die API — nur für `admin`

| Endpunkt | |
| -------- | - |
| `GET /monitoring/ereignisse?limit=&event=&severity=` | die jüngsten Einträge, neueste zuerst |
| `GET /monitoring/regeln` | welche Regeln greifen und ab wann |

`?severity=warning` zeigt genau das, was im Alltag interessiert: Fehlversuche, abgewiesene
Token, abgewehrte Zugriffe und die Treffer der Erkennung.

Beide Endpunkte verlangen `admin`. Wer den Trail lesen darf, sieht auch, welche Konten es
gibt und wann jemand arbeitet — das ist keine Auskunft für jeden, der sich anmelden kann.
Und beide sind **nur lesend**: Ein Audit-Trail, den man über die API löschen kann, ist
keiner. Aufgeräumt wird ausschließlich über den TTL-Index.

### Direkt in MongoDB

```bash
docker compose exec mongo mongosh medidoc --eval 'db.audit_events.find({severity:"warning"}).sort({ts:-1}).limit(20)'
```

## Wenn etwas ausfällt

**Kein MongoDB?** Die Anwendung startet trotzdem. Ist `MONGO_URL` leer oder Mongo nicht
erreichbar, läuft der Trail im Prozessspeicher (die letzten 5000 Ereignisse) und ist nach
dem Neustart weg. Das Log auf stdout bleibt vollständig. In diesem Modus laufen auch die
Tests und die CI — sie brauchen keinen Datenbank-Service.

**Mongo fällt im Betrieb aus?** Schreibfehler werden geschluckt und als Warnung geloggt.
`audit.service.record` **wirft nie**. Ein Arzt, der einen Patienten anlegen will, soll nicht
scheitern, weil die Audit-Datenbank hakt: Dann fehlt eine Zeile im Trail, aber die Praxis
arbeitet weiter. Die Zusicherung steht in `record` und nicht in einer einzelnen
Store-Ausführung, damit sie auch für eine künftige gilt.

## Einstellungen

Alle in der `.env` im Repo-Wurzelverzeichnis, Vorlage in `.env.example`.

| Variable | Vorgabe | |
| -------- | ------- | - |
| `LOG_LEVEL` | `INFO` | |
| `LOG_JSON` | `false` | im Container `true` |
| `MONGO_URL` | *(leer)* | leer = Trail im Speicher; Compose setzt `mongodb://mongo:27017` |
| `MONGO_DB` | `medidoc` | |
| `AUDIT_RETENTION_DAYS` | `30` | TTL-Index, MongoDB räumt selbst auf |
| `ABUSE_WINDOW_MINUTES` | `15` | Zeitfenster aller Regeln |
| `ABUSE_FAILED_LOGINS_PER_EMAIL` | `5` | |
| `ABUSE_FAILED_LOGINS_PER_IP` | `10` | |
| `ABUSE_REJECTED_TOKENS_PER_IP` | `10` | |
| `ABUSE_FORBIDDEN_PER_USER` | `3` | |
| `ABUSE_NOT_FOUND_PER_USER` | `20` | |

Die Schwellen stehen bewusst in der Konfiguration und nicht als Konstanten im Code: Beim
Vorführen will man sie einmal kleiner drehen, ohne eine Zeile zu ändern.

## Vorführen

```bash
# Schwelle herunterdrehen, damit es im Termin nicht dauert
ABUSE_FAILED_LOGINS_PER_EMAIL=3 docker compose up -d

# dreimal falsch anmelden
for i in 1 2 3; do
  curl -s -o /dev/null -X POST localhost:8000/auth/login \
    -d "username=anna.admin@medidoc.test&password=falsch"
done

# im Log steht jetzt eine Warnung "audit suspicious"
docker compose logs fastapi | grep suspicious
```

Und derselbe Befund über die API, nachdem man sich richtig angemeldet hat:

```bash
curl -s localhost:8000/monitoring/ereignisse?severity=warning \
  -H "Authorization: Bearer $TOKEN"
```

Das richtige Passwort meldet danach weiterhin an — es wird ja nicht blockiert.

## Tests

[`backend/tests/test_audit.py`](../backend/tests/test_audit.py), gegliedert nach
Anmeldeversuchen, Datensparsamkeit, Patientenänderungen, Missbrauch, Erkennung,
Monitoring-Endpunkt, Ausfallsicherheit und Anfrage-Kennung. Sie laufen gegen den
Speicher-Trail und brauchen kein MongoDB.

Die Tests unter `TestKeineGeheimnisseImTrail` sind nicht Beiwerk: Sie prüfen, dass weder
Passwort noch Token noch Patientenname je im Trail landen. Das ist die Regel, die beim
nächsten hinzugefügten Ereignis am leichtesten gebrochen wird.

## Nicht enthalten

Prometheus, Grafana, ein Log-Sammler wie Loki, verteiltes Tracing, Alarmierung per Mail
oder Chat. Alles davon wäre Infrastruktur, die jemand betreiben müsste, für einen Nutzen,
den `docker compose logs` und ein Endpunkt im Scope dieses Projekts genauso stiften.
`LOG_JSON=true` liefert bereits das Format, das ein Sammler erwartet — der Anschluss wäre
Konfiguration, keine Änderung am Code.
