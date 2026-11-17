from typing import Any
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "FindBack"
    APP_ENV: str = "development"
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    DATABASE_URL: str = "postgresql+asyncpg://findback:findback_secret@localhost:5432/findback"
    TEST_DATABASE_URL: str = "postgresql+asyncpg://findback:findback_secret@localhost:5432/findback_test"

    JWT_SECRET_KEY: str = "CHANGE_ME_DEV_SECRET_KEY_FOR_LOCAL_ONLY_12345"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            if v.strip() == "*":
                raise ValueError("CORS wildcard '*' is not allowed when allow_credentials=True.")
            if not v.startswith("["):
                origins = [i.strip() for i in v.split(",") if i.strip()]
                if any(o == "*" for o in origins):
                    raise ValueError("CORS wildcard '*' is not allowed when allow_credentials=True.")
                return origins
        elif isinstance(v, list):
            if any(o == "*" for o in v):
                raise ValueError("CORS wildcard '*' is not allowed when allow_credentials=True.")
            return v
        raise ValueError("Invalid CORS_ORIGINS configuration. Must be a list of explicit origin URLs.")

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.APP_ENV == "production":
            if not self.JWT_SECRET_KEY or "CHANGE_ME" in self.JWT_SECRET_KEY or len(self.JWT_SECRET_KEY) < 32:
                raise ValueError(
                    "JWT_SECRET_KEY must be a secure random secret of at least 32 characters in production."
                )
        return self

    @property
    def async_database_url(self) -> str:
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql+psycopg://"):
            return url.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)
        return url

    @property
    def async_test_database_url(self) -> str:
        url = self.TEST_DATABASE_URL
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql+psycopg://"):
            return url.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)
        return url


settings = Settings()
