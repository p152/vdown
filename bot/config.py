from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str

    vidbee_api_url: str = "http://vidbee-api:3100"
    telegram_bot_api_url: str = "http://telegram-bot-api:8081"
    downloads_dir: str = "/data/downloads"

    redis_url: str = "redis://redis:6379/0"
    database_url: str = "postgresql+asyncpg://vdown:vdown@postgres:5432/vdown"

    auto_max_duration_sec: int = 180
    auto_max_size_mb: int = 100
    max_concurrent_downloads: int = 3

    vidbee_proxy: str = ""
    vidbee_cookies_path: str = "/data/cookies/cookies.txt"

    admin_ids: str = ""
    feedback_chat_id: int | None = None

    free_daily_limit: int = 5

    crypto_bot_token: str = ""
    web_base_url: str = "http://localhost:8080"

    jwt_secret: str = "change-me-in-production"
    admin_web_password: str = ""
    jwt_expire_hours: int = 24


settings = Settings()


def admin_id_set() -> set[int]:
    if not settings.admin_ids.strip():
        return set()
    result: set[int] = set()
    for part in settings.admin_ids.split(","):
        part = part.strip()
        if part.isdigit():
            result.add(int(part))
    return result
