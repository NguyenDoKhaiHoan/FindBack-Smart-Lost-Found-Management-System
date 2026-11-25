from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env"), extra="ignore"
    )

    app_name: str = "FindBack API"
    app_env: str = "development"
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'findback.db').as_posix()}"
    database_schema: str = Field(default="findback_api", pattern=r"^[a-z][a-z0-9_]{0,62}$")
    jwt_secret_key: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "findback"
    jwt_audience: str = "findback-api"
    media_root: Path = BACKEND_DIR / "uploads"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    openai_api_key: SecretStr | None = None
    openai_chat_model: str = ""
    openai_vision_model: str = ""
    openai_timeout_seconds: float = Field(default=30, ge=1, le=60)
    ai_matching_enabled: bool = True
    ai_image_search_enabled: bool = True
    ai_auto_post_enabled: bool = True
    ai_chatbot_enabled: bool = True
    ai_cpu_threads: int = Field(default=2, ge=1, le=8)
    ai_text_backend: Literal["auto", "torch", "onnx", "details"] = "auto"
    ai_text_index_batch: int = Field(default=32, ge=4, le=128)
    ai_image_index_batch: int = Field(default=12, ge=1, le=64)
    ai_requests_per_minute: int = Field(default=12, ge=1, le=120)
    ai_global_requests_per_minute: int = Field(default=40, ge=1, le=240)

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
