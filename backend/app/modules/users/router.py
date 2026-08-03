"""Benutzerverwaltung — Endpunkte.

**Sprint 2, noch leer.** Anlegen, Deaktivieren und Rolle ändern gehören laut
ADR-0005 hierher und verlangen `admin`. In Sprint 1 entstehen Benutzer
ausschließlich über den Seed (`app/modules/users/seed.py`).

Der Router ist trotzdem schon eingehängt, damit später nur noch Endpunkte
dazukommen und niemand die Verdrahtung anfassen muss.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["users"])
