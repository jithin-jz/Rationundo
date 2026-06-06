from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/rationundo"
    source_database_url: str = "postgresql+psycopg2://postgres:password@localhost:5433/rationundo"


settings = Settings()
