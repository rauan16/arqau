from pathlib import Path
from typing import List, Literal

import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field, model_validator

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


Environment = Literal["development", "testing", "production"]
DEFAULT_DEVELOPMENT_SECRET_KEY = "arqau-development-only-secret"


def _environment_value() -> str:
    return os.getenv(
        "APP_ENV", os.getenv("ENVIRONMENT", os.getenv("ENV", "development"))
    ).strip().lower()


class Settings(BaseModel):
    environment: Environment = Field(default_factory=_environment_value)
    openai_api_key: str = Field(default="", repr=False)
    openai_model: str = "gpt-4o-mini"
    secret_key: str = Field(default="", repr=False)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14
    database_url: str = "sqlite+aiosqlite:///./arqau.db"
    cors_origins: str = "http://localhost:3000"
    jwt_issuer: str = "arqau"
    jwt_audience: str = "arqau-api"

    @model_validator(mode="after")
    def validate_production_settings(self):
        if self.environment != "production":
            if self.access_token_expire_minutes <= 0:
                raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be positive")
            if self.refresh_token_expire_days <= 0:
                raise ValueError("REFRESH_TOKEN_EXPIRE_DAYS must be positive")
            return self

        errors = []
        if not self.secret_key.strip() or self.secret_key == "arqau-secret-key-change-in-production":
            errors.append("SECRET_KEY must be set to a production-specific value")
        if not self.database_url:
            errors.append("DATABASE_URL is required")
        elif not self.is_postgresql:
            errors.append("DATABASE_URL must use PostgreSQL in production")
        if not self.openai_api_key.strip():
            errors.append("OPENAI_API_KEY is required")
        if self.access_token_expire_minutes <= 0:
            errors.append("ACCESS_TOKEN_EXPIRE_MINUTES must be positive")
        if self.refresh_token_expire_days <= 0:
            errors.append("REFRESH_TOKEN_EXPIRE_DAYS must be positive")
        if errors:
            raise ValueError("Production configuration is invalid: " + "; ".join(errors))
        return self

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_postgresql(self) -> bool:
        return self.database_url.startswith(("postgresql://", "postgresql+asyncpg://"))


def get_settings() -> Settings:
    environment = _environment_value()
    return Settings(
        environment=environment,
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        secret_key=(os.getenv("SECRET_KEY") or "").strip()
        or ("" if environment == "production" else DEFAULT_DEVELOPMENT_SECRET_KEY),
        algorithm=os.getenv("ALGORITHM", "HS256"),
        access_token_expire_minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")),
        refresh_token_expire_days=int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "14")),
        database_url=(os.getenv("DATABASE_URL") or "").strip()
        or ("" if environment == "production" else "sqlite+aiosqlite:///./arqau.db"),
        cors_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000"),
        jwt_issuer=os.getenv("JWT_ISSUER", "arqau"),
        jwt_audience=os.getenv("JWT_AUDIENCE", "arqau-api"),
    )
