from pathlib import Path
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict

# app/core/config.py -> app/core -> app -> backend -> Repo-Wurzel.
# Beim Verschieben dieser Datei muss die Zahl mitwandern.
REPO_ROOT = Path(__file__).resolve().parents[3]


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
