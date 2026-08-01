# PostgreSQL für Stammdaten, MongoDB für Dokumente

Wir setzen bewusst zwei Datenbanken ein, weil die beiden Datenarten unterschiedliche
Anforderungen haben. Patientenstammdaten sind streng strukturiert: Jeder Patient hat
dieselben Felder, und Beziehungen müssen konsistent bleiben — das ist der Normalfall für
PostgreSQL. Dokumente sind es nicht: Ein Laborwert hat völlig andere Felder als ein
Arztbrief, und neue Dokumenttypen sollen ohne Schemaänderung möglich sein. In PostgreSQL
hieße das eine breite Tabelle voller NULL-Werte oder eine Migration pro Dokumenttyp,
deshalb MongoDB.

## Wichtig: MongoDB speichert keine Dateien

Die Begründung für MongoDB ist die **Heterogenität der Metadaten**, nicht die Dateiablage.
Die Bytes eines Anhangs liegen auf einem Docker-Volume, in MongoDB steht nur der Pfad
darauf. Würden wir ausschließlich Dateien mit immer gleichen Feldern
(`dateiname, patient_id, datum, pfad`) speichern, gäbe es keinen Grund für eine zweite
Datenbank — das kann PostgreSQL genauso.

## Konsequenzen

- Zwei Datenbank-Services in Docker Compose, zwei Verbindungskonfigurationen.
- Referenzielle Integrität zwischen Patient und Dokument kann die Datenbank nicht
  erzwingen; die `patient_id` im Dokument ist eine Referenz ohne Fremdschlüssel.
- Diese Entscheidung ist ein zentraler Punkt der Abschlusspräsentation und muss von
  jedem im Team erklärbar sein.
