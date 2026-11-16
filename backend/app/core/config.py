from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env"), extra="ignore"
    )

    app_name: str = "FindBack Claims API"
    app_env: str = "development"
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'findback.db').as_posix()}"
    database_schema: str = Field(default="findback_api", pattern=r"^[a-z][a-z0-9_]{0,62}$")
    jwt_secret_key: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "findback"
    jwt_audience: str = "findback-api"

    @field_validator("jwt_secret_key")
    @classmethod
    def require_real_secret(cls, value: str) -> str:
        if "CHANGE_ME" in value.upper():
            raise ValueError("Configure a random JWT_SECRET_KEY of at least 32 characters")
        return value

    @field_validator("jwt_algorithm")
    @classmethod
    def supported_algorithm(cls, value: str) -> str:
        if value != "HS256":
            raise ValueError("This JWT adapter supports HS256 only")
        return value
