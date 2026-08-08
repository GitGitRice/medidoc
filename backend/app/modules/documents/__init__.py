"""Dokumente in der Akte eines Patienten.

Ein **Dokument** besteht aus Angaben, deren Felder vom **Dokumenttyp** abhängen,
und **optional** aus einem **Anhang** (CONTEXT.md). Die Begriffe sind die aus
CONTEXT.md, nicht „Datei", „Upload" oder „Attachment".

Wie `modules/audit/` ohne SQLModel-Tabelle: Die **Angaben** liegen in MongoDB,
die **Bytes eines Anhangs** auf einem Volume, die Patientenstammdaten weiterhin
in PostgreSQL ([ADR-0002](../../../../docs/adr/0002-postgres-fuer-stammdaten-mongodb-fuer-dokumente.md)).
Deshalb `store.py` statt `models.py` und zusätzlich `storage.py` für die Bytes.
"""
