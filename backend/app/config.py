from pydantic import BaseModel, EmailStr
from typing import Optional, List
import os
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseModel):
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 43200
    database_url: str = "sqlite+aiosqlite:///./arqau.db"
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]


def get_settings() -> Settings:
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        secret_key=os.getenv("SECRET_KEY", "arqau-secret-key-change-in-production"),
        algorithm=os.getenv("ALGORITHM", "HS256"),
        access_token_expire_minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "43200")),
        database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./arqau.db"),
        cors_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000"),
    )
