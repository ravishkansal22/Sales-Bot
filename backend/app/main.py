"""Ghost Negotiator – FastAPI application entry point.

Configures the FastAPI app with:
- Async lifespan manager for DB and Redis lifecycle
- CORS middleware (permissive for development)
- API router mounts for chat and simulation endpoints
- Root health-check / info endpoint
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.postgres import close_db, init_db
from app.services.redis_service import close_redis, init_redis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager.

    Initialises and tears down the database engine and Redis connection
    around the lifetime of the ASGI server.
    """
    logger.info("Starting Ghost Negotiator backend …")

    # Startup
    await init_db()
    await init_redis()

    yield

    # Shutdown
    await close_redis()
    await close_db()

    logger.info("Ghost Negotiator backend shut down cleanly")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Ghost Negotiator",
    description=(
        "AI-powered sales negotiation engine that simulates strategies, "
        "builds digital customer twins, and recommends optimal responses."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# CORS – allow all origins during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

# Lazy-import routers so that missing route modules do not crash the
# application at import time during early development.
try:
    from app.api.chat import router as chat_router

    app.include_router(chat_router, prefix="/api/v1", tags=["Chat"])
except ImportError:
    logger.warning("app.api.chat router not found – skipping mount")

try:
    from app.api.simulation import router as simulation_router

    app.include_router(simulation_router, prefix="/api/v1", tags=["Simulation"])
except ImportError:
    logger.warning("app.api.simulation router not found – skipping mount")

try:
    from app.api.catalog import router as catalog_router

    app.include_router(catalog_router)
except ImportError:
    logger.warning("app.api.catalog router not found – skipping mount")


# ---------------------------------------------------------------------------
# Root endpoint
# ---------------------------------------------------------------------------


@app.get("/", tags=["Health"])
async def root() -> dict[str, str]:
    """Root health-check endpoint.

    Returns basic application metadata so that uptime monitors and
    developers can verify the service is running.

    Returns:
        A dict containing the app name, version, and status.
    """
    return {
        "app": "Ghost Negotiator",
        "version": "0.1.0",
        "status": "operational",
    }


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Lightweight health-check endpoint for load balancers.

    Returns:
        A dict with ``{"status": "healthy"}``.
    """
    return {"status": "healthy"}
