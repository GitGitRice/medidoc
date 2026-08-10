"""Die Bytes eines Anhangs — auf der Platte, nicht in der Datenbank.

MongoDB hält die Angaben zum Dokument, hier liegen die Bytes. Warum getrennt,
steht in ADR-0002: Die Begründung für MongoDB ist die Heterogenität der
Angaben, nicht die Dateiablage.

> **Warum hier „Datei" steht und sonst „Anhang".** CONTEXT.md verbietet
> „Datei" als Wort für den *fachlichen* Begriff — das ist der **Anhang**. In
> dieser Datei geht es aber wirklich um Dateien auf einem Dateisystem: um
> Blöcke, Endungen und Pfade. Nur `storage.py` darf so reden.

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
        stream: BinaryIO,
        patient_id: int,
        document_id: str,
        attachment_id: str,
        filename: str | None,
        limit_bytes: int,
    ) -> StoredFile:
        """Schreibt die Datei und gibt Pfad und Größe zurück.

        Wirft `FileTooLarge` oder `EmptyFile` — und lässt in beiden Fällen
        nichts Halbes liegen.

        Ein Ordner je Dokument, darin eine Datei je Anhang: Seit ein Dokument
        mehrere Anhänge tragen kann, würde ein gemeinsamer Ordner sie nur über
        den Dateinamen auseinanderhalten — und der kommt vom Aufrufer.
        """
        folder = self.root / str(patient_id) / document_id
        folder.mkdir(parents=True, exist_ok=True)

        target = folder / f"{attachment_id}{safe_suffix(filename)}"
        # Erst unter einem Arbeitsnamen schreiben: Bricht der Upload ab, liegt
        # keine halbe Datei da, die wie eine ganze aussieht.
        partial = target.with_name(target.name + ".part")

        size = 0

        try:
            with partial.open("wb") as sink:
                while chunk := stream.read(CHUNK_SIZE):
                    size += len(chunk)
                    if size > limit_bytes:
                        raise FileTooLarge(limit_bytes)
                    sink.write(chunk)

            if size == 0:
                raise EmptyFile

            partial.replace(target)
        except BaseException:
            partial.unlink(missing_ok=True)
            raise

        return StoredFile(
            relative_path=str(target.relative_to(self.root)),
            size_bytes=size,
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

    def resolve(self, relative_path: str) -> Path:
        """Der volle Pfad zu einem gespeicherten Anhang.

        Nur für das Ausliefern gedacht. Der übergebene Pfad stammt aus den
        eigenen Angaben in MongoDB, nicht vom Aufrufer — trotzdem wird geprüft,
        dass er unterhalb der Wurzel bleibt: Ein zusammengesetzter Pfad, der aus
        dem Wurzelverzeichnis herausführt, wäre genau die Lücke, die
        `safe_suffix` beim Hochladen verhindert.
        """
        full = (self.root / relative_path).resolve()
        if not full.is_relative_to(self.root.resolve()):
            raise ValueError(f"Pfad liegt außerhalb der Ablage: {relative_path}")
        return full

    def delete_document_folder(self, patient_id: int, document_id: str) -> None:
        """Räumt den Ordner eines Dokuments samt aller Anhänge ab.

        Wie `delete`, nur für alle Anhänge auf einmal: Das Dokument ist beim
        Aufruf schon aus MongoDB verschwunden, ein Fehler hier darf die Antwort
        nicht mehr kippen.
        """
        try:
            shutil.rmtree(self.root / str(patient_id) / document_id)
        except FileNotFoundError:
            return
        except OSError:
            log.warning(
                "documents: Ordner des Dokuments nicht abgeräumt",
                extra={"patient_id": patient_id, "document_id": document_id},
                exc_info=True,
            )

    def delete_patient_folder(self, patient_id: int) -> None:
        """Räumt den Ordner eines Patienten samt Inhalt ab.

        Wird beim Löschen eines Patienten gebraucht: Ohne das blieben seine
        Dateien liegen, unerreichbar und trotzdem auf der Platte.

        Anders als `delete` schluckt diese Methode einen Fehler **nicht**. Dort
        geht es um eine einzelne Datei zu einem Dokument, das ohnehin schon weg
        ist; hier um alles, was von einem Patienten übrig ist. Bleibt davon
        etwas liegen, muss es jemand erfahren — eine `204` mit einer Zahl
        daneben behauptete sonst ein Aufräumen, das nicht stattgefunden hat.
        Ein Ordner, den es nie gab, ist kein Fehler.
        """
        folder = self.root / str(patient_id)
        try:
            shutil.rmtree(folder)
        except FileNotFoundError:
            return
        except OSError:
            log.error(
                "documents: Ordner des Patienten nicht abgeräumt",
                extra={"patient_id": patient_id},
                exc_info=True,
            )
            raise


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
