from pathlib import Path
from urllib.parse import quote_plus

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# app/core/config.py -> app/core -> app -> backend -> Repo-Wurzel.
# Beim Verschieben dieser Datei muss die Zahl mitwandern.
REPO_ROOT = Path(__file__).resolve().parents[3]

# Wohin Uploads gehen, wenn nichts anderes gesetzt ist.
DEFAULT_UPLOAD_DIR = REPO_ROOT / "uploads"


class Settings(BaseSettings):
    """Configuration read from the repo-root .env — the same file Docker Compose uses."""

    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    # Postgres — dieselben Variablen, die docker-compose.yml einsetzt.
    postgres_db: str
    postgres_user: str
    postgres_password: str
    postgres_port: int = 5432
    postgres_host: str = "localhost"  # im Compose-Netz: "postgres"

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480  # eine Praxis-Schicht, siehe docs/auth-api.md

    # Startbenutzer für den Seed. Feste Testzugangsdaten, kein Deployment-Stand.
    seed_admin_email: str
    seed_admin_password: str
    seed_staff_email: str
    seed_staff_password: str

    cors_origins: str = "http://localhost:5173"

    # Logging und Audit, siehe docs/logging-monitoring.md.
    log_level: str = "INFO"
    # Menschenlesbar beim lokalen Entwickeln, JSON im Container — dort liest es
    # `docker compose logs` und später ein Log-Sammler.
    log_json: bool = False

    # MongoDB für den Audit-Trail. Leer bedeutet: kein Mongo verfügbar, der
    # Trail läuft in den Speicher. Die Anwendung startet in beiden Fällen.
    mongo_url: str = ""
    mongo_db: str = "medidoc"

    # Dokumente, siehe docs/documents-api.md.
    # Wohin die hochgeladenen Dateien geschrieben werden. Im Container ein
    # Docker-Volume, lokal ein Ordner neben dem Code. Nur die Bytes liegen
    # hier — die Metadaten stehen in MongoDB (ADR-0002).
    upload_dir: str = str(DEFAULT_UPLOAD_DIR)
    # 20 MB. Ein Scan aus der Praxis liegt weit darunter; darüber ist es
    # entweder ein Versehen oder nichts, was in eine Akte gehört.
    max_upload_bytes: int = 20 * 1024 * 1024
    # Aufbewahrung. Mongo räumt selbst auf (TTL-Index), niemand muss putzen.
    audit_retention_days: int = 30

    # Schwellen der Missbrauchserkennung. Bewusst als Einstellung und nicht als
    # Konstante im Code: Beim Vorführen will man sie einmal kleiner drehen.
    abuse_window_minutes: int = 15
    abuse_failed_logins_per_email: int = 5
    abuse_failed_logins_per_ip: int = 10
    abuse_rejected_tokens_per_ip: int = 10
    abuse_forbidden_per_user: int = 3
    abuse_not_found_per_user: int = 20

    @field_validator("upload_dir")
    @classmethod
    def _leeres_upload_dir_ist_die_vorgabe(cls, wert: str) -> str:
        """`UPLOAD_DIR=` in der .env soll nicht ins Arbeitsverzeichnis schreiben.

        Eine leer gelassene Variable überschreibt den Standardwert sonst mit
        einem leeren String — und `Path("")` ist der Ordner, in dem der Prozess
        gerade steht. Das wäre bei den Uploads das Repo selbst.
        """
        return wert.strip() or str(DEFAULT_UPLOAD_DIR)

    @property
    def database_url(self) -> str:
        """Built from the POSTGRES_* variables so the password lives in one place only."""
        return (
            f"postgresql+psycopg://{self.postgres_user}:{quote_plus(self.postgres_password)}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
