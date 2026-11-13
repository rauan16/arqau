from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pathlib import Path
from app.config import get_settings
from app import database
from app.models import Base
from app.api.v1 import api_router
from app.core.body_limit import BodyLimitMiddleware
from app.core.logging_config import configure_logging, get_logger
from app.core.health import get_liveness, get_readiness
from app.core.exceptions import register_exception_handlers
from app.core.middleware import add_middleware

settings = get_settings()

# Configure logging at module load time
configure_logging(
    level=settings.environment == "production" and "INFO" or "DEBUG",
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Detect legacy local database (./arqau.db) to avoid polluting it during tests
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
            logger.warning("OPENAI_API_KEY is not set. AI endpoints will return errors.")
        yield
    finally:
        await database.dispose_engine()


app = FastAPI(title="ARQAU API", version="0.1.0", lifespan=lifespan)

# Register centralized exception handlers
register_exception_handlers(app)

# Add custom middleware (order matters - first added = outermost)
add_middleware(app)

# Add body limit middleware (before CORS to reject oversized payloads early)
app.add_middleware(BodyLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/live")
async def health_live():
    """Liveness probe - confirms process is alive."""
    return await get_liveness()


@app.get("/health/ready")
async def health_ready():
    """Readiness probe - confirms service can accept traffic."""
    readiness = await get_readiness()
    status_code = 200 if readiness.status == "ready" else 503
    return readiness


app.include_router(api_router)
