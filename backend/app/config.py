from pathlib import Path
from typing import List, Literal, Optional
from urllib.parse import urlparse

import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field, model_validator

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


Environment = Literal["development", "testing", "production"]
DEFAULT_DEVELOPMENT_SECRET_KEY = "arqau-development-only-secret"

# Known placeholder/weak secrets that should be rejected in production
KNOWN_WEAK_SECRETS = {
    "arqau-secret-key-change-in-production",
    "change-me",
    "change-me-in-production",
    "secret",
    "secretkey",
    "dev-secret",
    "test-secret",
    "placeholder",
    "your-secret-here",
    "your-secret-key-here",
}

# Minimum entropy threshold for production secret (characters)
MIN_SECRET_ENTROPY = 32

# Reasonable bounds for access token TTL (minutes)
MIN_ACCESS_TOKEN_TTL = 1
MAX_ACCESS_TOKEN_TTL = 1440  # 24 hours


def _validate_cors_origin(origin: str, environment: str) -> List[str]:
    """Validate a single CORS origin string."""
    errors = []

    # Reject empty
    if not origin.strip():
        errors.append("CORS origin cannot be empty")
        return errors

    # Reject wildcard
    if origin.strip() == "*":
        errors.append("CORS wildcard '*' is not allowed in production")
        return errors

    # Parse URL
    try:
        parsed = urlparse(origin.strip())
    except Exception:
        errors.append(f"Invalid CORS origin URL: {origin}")
        return errors

    # Must have scheme and netloc
    if not parsed.scheme or not parsed.netloc:
        errors.append(f"CORS origin must have scheme and host: {origin}")
        return errors

    # Reject non-HTTPS in production
    if environment == "production" and parsed.scheme.lower() != "https":
        errors.append(f"CORS origin must use HTTPS in production: {origin}")
        return errors

    # Allow HTTP for localhost in development
    if environment != "production" and parsed.scheme.lower() == "http":
        if not (parsed.hostname == "localhost" or parsed.hostname == "127.0.0.1"):
            errors.append(f"CORS origin must use HTTPS or be localhost in development: {origin}")
            return errors

    # Reject paths, queries, fragments
    if parsed.path not in ("", "/"):
        errors.append(f"CORS origin must not contain path: {origin}")
        return errors
    if parsed.query:
        errors.append(f"CORS origin must not contain query string: {origin}")
        return errors
    if parsed.fragment:
        errors.append(f"CORS origin must not contain fragment: {origin}")
        return errors

    # Reject credentials in URL
    if "@" in parsed.netloc:
        errors.append(f"CORS origin must not contain credentials: {origin}")
        return errors

    # Reject localhost/loopback in production
    if environment == "production":
        hostname = parsed.hostname.lower() if parsed.hostname else ""
        if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            errors.append(f"CORS origin must not be localhost in production: {origin}")
            return errors

    return errors


def _validate_cors_origins(cors_origins: str, environment: str) -> List[str]:
    """Validate CORS origins string (comma-separated)."""
    origins = [o.strip() for o in cors_origins.split(",") if o.strip()]

    if not origins:
        return ["CORS_ORIGINS must contain at least one origin"]

    all_errors = []
    for origin in origins:
        all_errors.extend(_validate_cors_origin(origin, environment))

    return all_errors


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
    # Number of trusted proxy hops. 0 = disabled (default).
    # When > 0, X-Forwarded-For is parsed and the IP at position [-trusted_proxy_count] is used.
    trusted_proxy_count: int = 0
    openai_max_tokens: int = 900
    openai_base_url: Optional[str] = Field(default="", repr=False)

    @model_validator(mode="after")
    def validate_production_settings(self):
        if self.environment != "production":
            if self.access_token_expire_minutes <= 0:
                raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be positive")
            if self.refresh_token_expire_days <= 0:
                raise ValueError("REFRESH_TOKEN_EXPIRE_DAYS must be positive")
            return self

        errors = []
        # Secret key validation
        if not self.secret_key.strip():
            errors.append("SECRET_KEY must be set to a production-specific value")
        elif self.secret_key == "arqau-secret-key-change-in-production":
            errors.append("SECRET_KEY must be set to a production-specific value")
        elif self.secret_key in KNOWN_WEAK_SECRETS:
            errors.append("SECRET_KEY must not be a known weak or placeholder value")
        elif len(self.secret_key) < MIN_SECRET_ENTROPY:
            errors.append(f"SECRET_KEY must be at least {MIN_SECRET_ENTROPY} characters for production")

        # JWT issuer/audience validation
        if not self.jwt_issuer.strip():
            errors.append("JWT_ISSUER must be set and non-empty")
        if not self.jwt_audience.strip():
            errors.append("JWT_AUDIENCE must be set and non-empty")

        # Access token TTL bounds
        if not (MIN_ACCESS_TOKEN_TTL <= self.access_token_expire_minutes <= MAX_ACCESS_TOKEN_TTL):
            errors.append(f"ACCESS_TOKEN_EXPIRE_MINUTES must be between {MIN_ACCESS_TOKEN_TTL} and {MAX_ACCESS_TOKEN_TTL}")

        # CORS origins validation
        cors_errors = _validate_cors_origins(self.cors_origins, self.environment)
        errors.extend(cors_errors)

        if not self.database_url:
            errors.append("DATABASE_URL is required")
        elif not self.is_postgresql:
            errors.append("DATABASE_URL must use PostgreSQL in production")
        if not self.openai_api_key.strip():
            errors.append("OPENAI_API_KEY is required")
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
        openai_base_url=os.getenv("OPENAI_BASE_URL"),
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
        trusted_proxy_count=int(os.getenv("TRUSTED_PROXY_COUNT", "0")),
        openai_max_tokens=int(os.getenv("OPENAI_MAX_TOKENS", "900")),
    )
