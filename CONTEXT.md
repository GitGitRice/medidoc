# MediDoc

Eine digitale Patientenakte für Arztpraxen. Die Praxis verwaltet ihre Patienten und die
zu ihnen gehörenden Dokumente an einem Ort.

## Language

**Patient**:
Eine Person, die in der Praxis behandelt wird. Zentrale Einheit der Anwendung — alles
andere hängt an einem Patienten.
_Avoid_: Kunde, Klient, Fall

**Akte**:
Die Gesamtheit aller Daten zu einem Patienten — Stammdaten und Dokumente. Es gibt genau
eine Akte pro Patient; "Akte" und "Patient" sind daher keine getrennten Objekte, sondern
zwei Sichten auf dasselbe.
_Avoid_: Patientenakte (als eigenes Objekt), Dossier, Fallakte

**Stammdaten**:
Die beständigen Daten eines Patienten — Name, Geburtsdatum, Kontakt, Versicherung.
Ändern sich selten und gehören dem Patienten selbst, nicht einem einzelnen Besuch.
_Avoid_: Profil, Grunddaten

**Dokument**:
Ein Eintrag in der Akte eines Patienten — z. B. ein Befund oder ein Laborwert. Besteht
aus beschreibenden Angaben — Titel, Beschreibung, Schlagworte, Dokumenttyp — und aus
beliebig vielen Anhängen. Gehört immer zu genau einem Patienten.
_Avoid_: Datei, Upload, Eintrag

**Dokumenttyp**:
Die Art eines Dokuments — z. B. Befund, Arztbrief, Laborwert. Ein Schlagwort zum Sortieren
und Filtern. Neue Dokumenttypen sollen ohne Schemaänderung möglich sein; der Typ bestimmt
**nicht**, welche Felder ein Dokument hat — alle Dokumente haben dieselben.

Typabhängige Felder sind nicht verworfen, sondern **vertagt**: Sie setzen einen Katalog je
Dokumenttyp voraus, der festlegt, welche Felder es gibt. Ohne ihn schriebe der eine `hb`,
der nächste `Hb` und der dritte `haemoglobin` — drei Schlüssel für denselben Wert, und
keine Auswertung fände sie zusammen. Erst der Katalog, dann die Felder.
_Avoid_: Kategorie, Art, Klasse

**Anhang**:
Die eigentliche Datei zu einem Dokument, etwa ein PDF oder ein Scan. Ein Dokument kann
beliebig viele Anhänge haben — ein Befund aus drei gescannten Seiten ist **ein** Dokument
mit drei Anhängen. Ein Dokument ohne Anhang ist gültig. Jeder Anhang trägt seine eigene
Herkunft; die Anhänge eines Dokuments können aus verschiedenen Quellen stammen.
_Avoid_: Datei, Attachment, Upload

**Benutzer**:
Eine Person, die sich in MediDoc anmeldet — also Praxispersonal, nicht der Patient.
Ob zwischen Arzt und MFA unterschieden wird, ist bewusst offen.
_Avoid_: User, Account, Nutzer

**Patientenübersicht**:
Die Listenansicht aller Patienten der Praxis — der Einstiegspunkt der Anwendung.
_Avoid_: Dashboard, Patiententabelle
