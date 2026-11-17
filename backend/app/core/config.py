from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "ScoutSphere"
    environment: str = "local"  # local | test | staging | production
    debug: bool = False
    version: str = "0.1.0"

    database_url: str = "postgresql+asyncpg://scoutsphere:scoutsphere@localhost:5433/scoutsphere"
    redis_url: str = "redis://localhost:6380/0"

    cors_origins: list[str] = ["http://localhost:3000"]

    @property
    def sync_database_url(self) -> str:
        """Sync URL used by Alembic."""
        return self.database_url.replace("+asyncpg", "+psycopg2")


@lru_cache
def get_settings() -> Settings:
    return Settings()
