"""Audit-Trail und Missbrauchserkennung.

Ein Modul wie jedes andere unter `app/modules/`, mit einer Besonderheit: Es hat
keine SQLModel-Tabelle. Der Trail liegt in MongoDB, nicht in Postgres — warum,
steht in docs/adr/0007-mongodb-fuer-audit-und-monitoring.md.

Deshalb hat dieses Modul `store.py` statt `models.py`.
"""
