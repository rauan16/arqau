"""FastAPI application entrypoint for the ARQAU MVP.

Keep this entrypoint self-contained: the release branch intentionally contains
only the middleware and support modules required by the deployed MVP.
"""

from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import database
from app.api.v1 import api_router
from app.config import get_settings
from app.core.body_limit import BodyLimitMiddleware
from app.models import Base

settings = get_settings()

# Stable Vercel alias for the investor/demo release branch. Unlike a
# deployment-specific preview hostname, this alias remains constant across
# commits, so browser requests keep passing CORS after each preview deploy.
PREVIEW_CORS_ORIGINS = (
    "https://arqau-git-release-v10-demo-rauanserikov77-9300s-projects.vercel.app",
)
allowed_cors_origins = list(dict.fromkeys([
    *settings.cors_origins_list,
    *PREVIEW_CORS_ORIGINS,
]))

logging.basicConfig(
    level=logging.INFO if settings.environment == "production" else logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("arqau.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Production schema changes are managed by Alembic before Uvicorn starts.
        # For local development, create missing tables unless this is the legacy
        # database file that must remain untouched.
        engine_url = database.engine.url
        is_legacy_db = (
            engine_url.drivername == "sqlite+aiosqlite"
            and engine_url.database is not None
            and Path(engine_url.database).resolve() == Path("./arqau.db").resolve()
        )
        if settings.environment != "production" and not is_legacy_db:
            async with database.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

        if not settings.openai_api_key:
            logger.warning("OPENAI_API_KEY is not set; AI endpoints will use their configured fallback.")
        yield
    finally:
        await database.dispose_engine()


app = FastAPI(title="ARQAU API", version="0.1.0", lifespan=lifespan)

# Reject oversized request payloads before CORS/auth/route processing.
app.add_middleware(BodyLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/live")
async def health_live():
    return {"status": "ok"}


app.include_router(api_router)
