from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/rationundo"
    source_database_url: str = "postgresql+psycopg2://postgres:password@localhost:5433/rationundo"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
