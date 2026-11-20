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

    # Both loopback spellings: browsers treat localhost and 127.0.0.1 as different origins.
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    frontend_url: str = "http://localhost:3000"
    invitation_days: int = 7

    # Auth. jwt_secret MUST be overridden outside local/test (enforced in security.py).
    jwt_secret: str = "dev-only-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 14
    refresh_cookie_name: str = "refresh_token"
    cookie_secure: bool = False  # True behind HTTPS in staging/production

    # Uploaded media (player photos). Local disk now; the storage layer is an interface so
    # object storage (S3 / MinIO) can replace it without touching callers.
    media_root: str = "media"
    photo_max_bytes: int = 5 * 1024 * 1024
    media_url_hours: int = 24  # lifetime of signed photo URLs (rounded to stay cacheable)

    @property
    def sync_database_url(self) -> str:
        """Sync URL used by Alembic."""
        return self.database_url.replace("+asyncpg", "+psycopg2")


@lru_cache
def get_settings() -> Settings:
    return Settings()
