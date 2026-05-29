from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://opsflow:opsflow@localhost:5432/opsflow"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me-in-production"
    access_token_expire_minutes: int = 1440

    ai_provider: str = "mock"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash-lite"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()