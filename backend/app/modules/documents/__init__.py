"""Dokumente zu einem Patienten — Datei plus Angaben dazu.

Wie `modules/audit/` ohne SQLModel-Tabelle: Die **Metadaten** liegen in
MongoDB, die **Bytes** auf einem Volume, die Patientenstammdaten weiterhin in
PostgreSQL (ADR-0002). Deshalb `store.py` statt `models.py` und zusätzlich
`storage.py` für die Dateien selbst.
"""
