from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central, typed application configuration.
    Values are read from environment variables / a .env file.
    Never hardcode secrets here — this class only defines shape + defaults.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_name: str = "legal-chatbot-api"
    app_env: str = "development"
    debug: bool = True

    # Database
    database_url: str

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth / JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # File uploads
    max_upload_size_mb: int = 20


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings instance. Import and call get_settings() anywhere
    you need config instead of instantiating Settings() directly —
    this avoids re-reading .env on every call and makes testing easier
    (you can override the cache in tests).
    """
    return Settings()
