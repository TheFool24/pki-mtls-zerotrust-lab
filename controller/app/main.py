"""FastAPI application entry point.

Service: thesis-controller
Role: Master controller for PKI/mTLS/Zero Trust lab
Author: jojo (ВУТП, 2026)
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import audit, health, nodes, whoami
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown hooks."""
    configure_logging()
    log = get_logger("startup")
    log.info(
        "controller_starting",
        service=settings.service_name,
        version=settings.service_version,
        environment=settings.environment,
    )

    # Initialize DB (creates tables + sets pragmas)
    await init_db()

    yield
    log.info("controller_stopping")


app = FastAPI(
    title="Thesis Lab Controller",
    description="Master controller for PKI / mTLS / Zero Trust laboratory",
    version=settings.service_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)

# API v1 routes
app.include_router(health.router, prefix="/api/v1")
app.include_router(whoami.router, prefix="/api/v1")
app.include_router(nodes.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
