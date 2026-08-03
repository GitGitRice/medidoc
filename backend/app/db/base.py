"""Modell-Register und Tabellenanlage.

`SQLModel.metadata` kennt nur Tabellen, deren Modul vorher importiert wurde.
Deshalb ist das hier die **eine** Stelle, die alle Module kennt — ein neues
Modul mit Tabellen trägt sich mit genau einer Import-Zeile ein. Sonst fehlt
seine Tabelle beim Anlegen, ohne dass irgendwo ein Fehler auftaucht.

Umgekehrt importiert kein Modul diese Datei. Die Abhängigkeit läuft nur in
eine Richtung, damit die Module untereinander frei bleiben.
"""

from sqlmodel import SQLModel

from app.db.session import engine

# Nur wegen der Nebenwirkung importiert: Registrierung in SQLModel.metadata.
from app.modules.patients import models as patient_models  # noqa: F401
from app.modules.users import models as user_models  # noqa: F401


def init_db() -> None:
    """Legt alle noch fehlenden Tabellen an.

    Wird vom Seed aufgerufen, nicht beim Start der App — die API soll auch
    dann booten, wenn Postgres gerade nicht läuft.

    `create_all` legt nur an, was fehlt. Geänderte Spalten zieht es **nicht**
    nach: Wer ein bestehendes Modell ändert, muss die Tabelle lokal wegwerfen
    (`docker compose down -v`). Migrationen sind für Sprint 1 bewusst kein Thema.
    """
    SQLModel.metadata.create_all(engine)
