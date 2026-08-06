"""Die Bytes einer hochgeladenen Datei — auf der Platte, nicht in der Datenbank.

MongoDB hält die Angaben zum Dokument, hier liegt die Datei selbst. Warum
getrennt, steht in ADR-0002: Die Begründung für MongoDB ist die Heterogenität
der Metadaten, nicht die Dateiablage.

Zwei Dinge, auf die es in dieser Datei ankommt:

**Der Dateiname des Aufrufers wird nie zum Pfad.** Er kommt aus dem Browser und
darf alles enthalten — `../../etc/passwd` ebenso wie einen Patientennamen.
Gespeichert wird unter der selbst vergebenen Dokument-Kennung; der ursprüngliche
Name überlebt nur als Angabe in den Metadaten.

**Die Größe wird beim Schreiben geprüft, nicht danach.** Erst alles einlesen und
dann die Länge messen hieße, dass eine 2-GB-Datei zuerst vollständig im
Speicher landet. Stattdessen wird in Blöcken gelesen und beim Überschreiten
sofort abgebrochen.
"""

import hashlib
import logging
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

log = logging.getLogger(__name__)

# 1 MiB je Block: groß genug, dass 20 MB in zwanzig Durchläufen durch sind,
# klein genug, dass ein Abbruch nicht erst nach der halben Datei greift.
CHUNK_SIZE = 1024 * 1024

# Aus dem Dateinamen des Aufrufers wird höchstens das hier übernommen.
_SAFE_SUFFIX = re.compile(r"^\.[A-Za-z0-9]{1,10}$")


class FileTooLarge(Exception):
    """Die Datei überschreitet das erlaubte Maß."""

    def __init__(self, limit_bytes: int) -> None:
        super().__init__(f"Datei ist größer als {limit_bytes} Bytes")
        self.limit_bytes = limit_bytes


class EmptyFile(Exception):
    """Null Bytes — entweder ein Versehen oder ein leeres Formularfeld."""


@dataclass(frozen=True)
class StoredFile:
    """Was nach dem Speichern über die Datei bekannt ist."""

    relative_path: str
    size_bytes: int
    sha256: str


def safe_suffix(filename: str | None) -> str:
    """Die Dateiendung — aber nur, wenn sie harmlos aussieht.

    `"befund.pdf"` ergibt `".pdf"`, `"böse.pdf.exe.../x"` ergibt `""`. Die
    Endung dient allein dazu, dass eine Datei auf der Platte erkennbar bleibt;
    verlassen tut sich darauf nichts.
    """
    if not filename:
        return ""
    suffix = Path(filename).suffix
    return suffix if _SAFE_SUFFIX.match(suffix) else ""


class FileStorage:
    """Schreibt und löscht Dateien unterhalb eines festen Wurzelverzeichnisses."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def save(
        self,
        quelle: BinaryIO,
        patient_id: int,
        document_id: str,
        filename: str | None,
        limit_bytes: int,
    ) -> StoredFile:
        """Schreibt die Datei und gibt Größe und Prüfsumme zurück.

        Wirft `FileTooLarge` oder `EmptyFile` — und lässt in beiden Fällen
        nichts Halbes liegen.
        """
        ordner = self.root / str(patient_id)
        ordner.mkdir(parents=True, exist_ok=True)

        ziel = ordner / f"{document_id}{safe_suffix(filename)}"
        # Erst unter einem Arbeitsnamen schreiben: Bricht der Upload ab, liegt
        # keine halbe Datei da, die wie eine ganze aussieht.
        arbeitsdatei = ziel.with_name(ziel.name + ".part")

        pruefsumme = hashlib.sha256()
        groesse = 0

        try:
            with arbeitsdatei.open("wb") as senke:
                while block := quelle.read(CHUNK_SIZE):
                    groesse += len(block)
                    if groesse > limit_bytes:
                        raise FileTooLarge(limit_bytes)
                    pruefsumme.update(block)
                    senke.write(block)

            if groesse == 0:
                raise EmptyFile

            arbeitsdatei.replace(ziel)
        except BaseException:
            arbeitsdatei.unlink(missing_ok=True)
            raise

        return StoredFile(
            relative_path=str(ziel.relative_to(self.root)),
            size_bytes=groesse,
            sha256=pruefsumme.hexdigest(),
        )

    def delete(self, relative_path: str) -> None:
        """Entfernt eine Datei. Eine schon fehlende ist kein Fehler.

        Der Aufrufer hat den Metadaten-Eintrag bereits gelöscht; scheiterte das
        Entfernen der Datei hier mit einer Ausnahme, bliebe die Antwort ein
        Fehler, obwohl das Dokument aus Sicht der Anwendung weg ist.
        """
        try:
            (self.root / relative_path).unlink(missing_ok=True)
        except OSError:
            log.warning(
                "documents: Datei nicht gelöscht",
                extra={"path": relative_path},
                exc_info=True,
            )

    def delete_patient_folder(self, patient_id: int) -> None:
        """Räumt den Ordner eines Patienten ab. Für Aufräumarbeiten."""
        shutil.rmtree(self.root / str(patient_id), ignore_errors=True)


_storage: FileStorage | None = None


def get_storage() -> FileStorage:
    """Die Dateiablage dieser Anwendung."""
    global _storage
    if _storage is None:
        from app.core.config import settings

        _storage = FileStorage(settings.upload_dir)
    return _storage


def set_storage(storage: FileStorage | None) -> None:
    """Setzt die Ablage — für Tests, und um sie wieder zurückzusetzen."""
    global _storage
    _storage = storage
