# AWS-Demo-Deployment

MediDoc läuft für die Projektvorführung auf einer EC2-Instanz in der Region
`eu-central-1` (Frankfurt). Das Deployment ergänzt die lokale Entwicklung; der
lokale Start mit `docker compose up` bleibt unverändert.

## Öffentliche Adressen

- Frontend: <http://ec2-52-28-116-149.eu-central-1.compute.amazonaws.com:5173>
- API-Dokumentation: <http://ec2-52-28-116-149.eu-central-1.compute.amazonaws.com:8000/docs>
- API-Healthcheck: <http://ec2-52-28-116-149.eu-central-1.compute.amazonaws.com:8000/health>

Die Elastic IP `52.28.116.149` ist fest mit der Instanz verbunden. IP und DNS-Name
bleiben deshalb auch nach einem Stoppen und erneuten Starten gleich. Die Adresse wird
berechnet, solange sie im AWS-Konto reserviert ist, und muss nach Projektende wieder
freigegeben werden.

## Architektur

Alle vier Anwendungsdienste laufen mit Docker Compose auf derselben EC2-Instanz:

```text
Internet
  ├── :5173 → React/Vite
  └── :8000 → FastAPI
                    ├── PostgreSQL :5432 (nicht öffentlich)
                    └── MongoDB    :27017 (nicht öffentlich)
```

| AWS-Ressource | Konfiguration |
| --- | --- |
| Region | `eu-central-1` |
| EC2 | `t2.micro`, Amazon Linux 2023, 1 vCPU, 1 GiB RAM |
| EBS | 20 GiB `gp3`, verschlüsselt, beim Terminieren mit löschen |
| Elastic IP | `52.28.116.149`, Name `medidoc-demo-eip` |
| Swap | 2 GiB auf dem EBS-Volume |
| IAM Instance Profile | `EC2-SSM-Role` mit `AmazonSSMManagedInstanceCore` |
| Security Group | `medidoc-demo-sg` |
| Administration | AWS Systems Manager Session Manager, kein offener SSH-Port |

Die Security Group erlaubt eingehend nur TCP `5173` und `8000` aus dem Internet.
Compose bindet die Datenbankports `5432` und `27017` auf der AWS-Instanz zusätzlich
nur an `127.0.0.1`; die AWS-Firewall bleibt damit eine zweite Schutzschicht. Port
`22` bleibt ebenfalls geschlossen.

## Vollständige Neuerstellung über die AWS-Konsole

### 1. IAM-Rolle für Session Manager

Unter **IAM → Roles → Create role** eine Rolle mit diesen Werten anlegen:

1. Trusted entity type: **AWS service**
2. Use case: **EC2**
3. Policy: `AmazonSSMManagedInstanceCore`
4. Role name: `EC2-SSM-Role`

Die AWS-Konsole erzeugt dabei automatisch das gleichnamige Instance Profile. Existiert
die Rolle bereits, wird sie wiederverwendet. Ein SSH-Schlüssel ist für die Verwaltung
über Session Manager nicht erforderlich.

### 2. Security Group

Unter **EC2 → Network & Security → Security Groups → Create security group** in der
VPC der späteren Instanz `medidoc-demo-sg` anlegen.

Eingehende Regeln:

| Typ | Port | Quelle | Zweck |
| --- | ---: | --- | --- |
| Custom TCP | `5173` | `0.0.0.0/0` | öffentliches Frontend |
| Custom TCP | `8000` | `0.0.0.0/0` | öffentliche API |

Die ausgehende Standardregel **All traffic → `0.0.0.0/0`** bleibt bestehen, damit
die Instanz AWS Systems Manager, GitHub, Docker Hub und Paketquellen erreicht. Keine
eingehenden Regeln für SSH `22`, PostgreSQL `5432` oder MongoDB `27017` anlegen.

### 3. EC2-Instanz starten

Unter **EC2 → Instances → Launch instances** konfigurieren:

| Feld | Wert |
| --- | --- |
| Name | `medidoc-demo` |
| AMI | Amazon Linux 2023, Standard-AMI, x86_64 |
| Instance type | `t2.micro` |
| Key pair | ohne Key Pair fortfahren |
| VPC | Default-VPC beziehungsweise dieselbe VPC wie die Security Group |
| Subnet | öffentliches Subnetz |
| Auto-assign public IP | aktiviert |
| Security Group | vorhandene `medidoc-demo-sg` auswählen |
| Storage | 20 GiB `gp3`, verschlüsselt, Delete on termination aktiviert |

Unter **Advanced details** zusätzlich setzen:

- IAM instance profile: `EC2-SSM-Role`
- Metadata version: **V2 only (token required)**
- User data: vollständigen Inhalt von
  [deploy/aws/bootstrap.sh](../deploy/aws/bootstrap.sh) einfügen

Danach **Launch instance** wählen. Der Bootstrap kann auf der kleinen Instanz wegen
der Image-Downloads und Builds mehrere Minuten dauern.

### 4. Bootstrap und Container prüfen

Warten, bis beide EC2-Statuschecks erfolgreich sind. Danach unter **EC2 → Instances →
medidoc-demo → Connect → Session Manager → Connect** ein Browser-Terminal öffnen.

```bash
sudo cloud-init status
sudo tail -n 100 /var/log/medidoc-bootstrap.log
cd /opt/medidoc
sudo docker compose ps
```

Der Bootstrap ist fertig, wenn alle vier Services laufen und PostgreSQL sowie MongoDB
als `healthy` angezeigt werden. Der API-Prozess besitzt absichtlich keinen
Compose-Healthcheck; er wird über `/health` geprüft.

### 5. Elastic IP zuweisen

Unter **EC2 → Network & Security → Elastic IP addresses**:

1. **Allocate Elastic IP address** wählen.
2. Amazon-Pool und Region `eu-central-1` verwenden.
3. Tag `Name=medidoc-demo-eip` setzen und die Adresse reservieren.
4. Die neue Adresse markieren und **Actions → Associate Elastic IP address** wählen.
5. Resource type **Instance** und `medidoc-demo` auswählen.

Danach in den Instanzdetails den neuen **Public IPv4 DNS** kopieren. Weil der
Bootstrap zunächst den automatisch vergebenen DNS-Namen kannte, müssen in
`/opt/medidoc/.env` diese drei Werte auf den neuen Namen gesetzt werden:

```dotenv
CORS_ORIGINS=http://NEUER_EC2_DNS_NAME:5173
VITE_API_URL=http://NEUER_EC2_DNS_NAME:8000
VITE_ALLOWED_HOST=NEUER_EC2_DNS_NAME
```

Datei über Session Manager bearbeiten und nur API und Frontend neu erstellen:

```bash
sudo nano /opt/medidoc/.env
cd /opt/medidoc
sudo docker compose up -d --no-deps --force-recreate fastapi frontend
```

Die Elastic IP bleibt bei einem Stoppen und Starten erhalten. Sie wird jedoch
berechnet, solange sie im AWS-Konto reserviert ist – auch bei gestoppter Instanz.

### 6. Deployment abnehmen

Im Browser Frontend und API-Dokumentation über den neuen DNS-Namen öffnen. Auf der
Instanz zusätzlich prüfen:

```bash
curl --fail http://localhost:8000/health
cd /opt/medidoc
sudo docker compose ps
```

Erwartete Health-Antwort:

```json
{"status":"ok"}
```

Danach mit den in `/home/ec2-user/medidoc-demo-login.txt` abgelegten Demo-Daten die
Anmeldung über das Frontend testen.

## Automatischer Bootstrap

Beim ersten Start wird [deploy/aws/bootstrap.sh](../deploy/aws/bootstrap.sh) als EC2
User Data ausgeführt. Das Skript:

1. aktualisiert Amazon Linux und installiert Docker sowie Git,
2. installiert kompatible Versionen von Docker Compose und Buildx,
3. richtet wegen des kleinen Arbeitsspeichers 2 GiB Swap ein,
4. klont den Branch `develop` nach `/opt/medidoc`,
5. erzeugt zufällige Datenbank-, JWT- und Demo-Passwörter,
6. bindet beide Datenbankports nur an die lokale Schnittstelle,
7. startet alle Services und legt 25 erfundene Testpatienten an.

Der Bootstrap ist ausschließlich für die Ersteinrichtung gedacht. Existiert bereits
`/opt/medidoc/.env`, bricht er ab, bevor Repository oder Zugangsdaten überschrieben
werden. Aktualisierungen erfolgen stattdessen mit den Befehlen im nächsten Abschnitt.

Die erzeugte `.env` liegt nur auf der Instanz und wird nicht eingecheckt. Die
Demo-Zugangsdaten können nach dem Verbinden über Session Manager gelesen werden:

```bash
sudo cat /home/ec2-user/medidoc-demo-login.txt
```

## Betrieb

In der AWS-Konsole unter **EC2 → Instances → medidoc-demo → Connect → Session
Manager** eine Sitzung öffnen. Status und Logs werden dort so geprüft:

```bash
cd /opt/medidoc
sudo docker compose ps
sudo docker compose logs --tail=100
```

Den Stand von `develop` aktualisieren und neu bauen:

```bash
cd /opt/medidoc
sudo git pull --ff-only origin develop
sudo docker compose up -d --build
sudo docker compose exec -T fastapi python -m app.seed --patients 25
```

Container anhalten, Daten-Volumes aber behalten:

```bash
cd /opt/medidoc
sudo docker compose down
```

`docker compose down -v` löscht zusätzlich PostgreSQL-, MongoDB- und
Dokument-Volumes und darf nur verwendet werden, wenn die Demo-Daten nicht mehr
gebraucht werden.

## Ressourcen nach Projektende entfernen

Die Reihenfolge ist wichtig, damit keine Elastic IP unbemerkt weiterberechnet wird:

1. Unter **EC2 → Elastic IP addresses** `medidoc-demo-eip` auswählen.
2. **Actions → Disassociate Elastic IP address** ausführen.
3. Anschließend **Actions → Release Elastic IP addresses** ausführen.
4. Unter **EC2 → Instances** `medidoc-demo` terminieren.
5. Prüfen, dass das Root-EBS-Volume automatisch gelöscht wurde.
6. Die Security Group `medidoc-demo-sg` löschen, wenn sie nicht mehr verwendet wird.
7. Die Rolle `EC2-SSM-Role` nur löschen, wenn sie keine andere Instanz benötigt.

**Stoppen** beendet lediglich die Rechenkosten der Instanz; EBS-Speicher und eine
reservierte Elastic IP bleiben bestehen. **Terminieren** entfernt die Instanz und das
als `Delete on termination` konfigurierte Root-Volume endgültig.

## Grenzen des Demo-Deployments

Das Deployment arbeitet bewusst mit HTTP, dem Vite-Entwicklungsserver und
ausschließlich erfundenen Testdaten. Es ist ein überprüfbarer Projekt- und
Schulungsstand, aber keine geeignete Produktionsumgebung für echte Patientendaten.
Für Produktion wären unter anderem HTTPS, eine feste Domain, Backups, getrennte
Netze und ein eigener Umgang mit Secrets erforderlich.
