from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # The repository-root .env is read whether the app runs from the root (Docker, tests via
    # env vars) or from backend/; a backend/.env, if present, overrides it.
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

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
    # Short-lived: a token keeps working until it expires, even after logout.
    access_token_minutes: int = 5
    refresh_token_days: int = 14
    refresh_cookie_name: str = "refresh_token"
    cookie_secure: bool = False  # True behind HTTPS in staging/production

    # Sign-in throttling (counted in Redis). Failures per email address and per IP address
    # within the window; reaching the limit blocks further attempts until the window ends.
    login_window_minutes: int = 15
    login_max_failures_per_account: int = 5
    login_max_failures_per_ip: int = 30

    # Uploaded media (player photos). Local disk now; the storage layer is an interface so
    # object storage (S3 / MinIO) can replace it without touching callers.
    media_root: str = "media"
    photo_max_bytes: int = 5 * 1024 * 1024
    # Signed photo URLs live 1 to 2 of these windows (rounded so a URL stays cacheable).
    # A leaked link stops working within hours, not days.
    media_url_hours: int = 2

    @property
    def sync_database_url(self) -> str:
        """Sync URL used by Alembic."""
        return self.database_url.replace("+asyncpg", "+psycopg2")


@lru_cache
def get_settings() -> Settings:
    return Settings()
