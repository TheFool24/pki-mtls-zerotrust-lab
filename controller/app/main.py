"""FastAPI application entry point with Prometheus instrumentation.

Service: thesis-controller
Role: Master controller for PKI/mTLS/Zero Trust lab
Author: jojo (ВУТП, 2026)
"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.api import audit, health, nodes, whoami
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.metrics_hooks import periodic_gauge_refresh
from app.core.revocation import periodic_crl_refresh
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
    await init_db()

    # Background task: refresh gauges every 30s
    gauge_task = asyncio.create_task(periodic_gauge_refresh(interval_seconds=30))
    # Background task: refresh the revoked-serial cache from step-ca's CRL
    crl_task = asyncio.create_task(periodic_crl_refresh())

    yield

    log.info("controller_stopping")
    for task in (gauge_task, crl_task):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Thesis Lab Controller",
    description="Master controller for PKI / mTLS / Zero Trust laboratory",
    version=settings.service_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)

# Prometheus instrumentation — automatic HTTP metrics + /metrics endpoint.
# NOTE: /metrics is exposed WITHOUT mTLS at controller level. Nginx does not
# proxy /metrics, so it is reachable only from inside the Docker network
# (Prometheus scrapes controller:8000/metrics directly) — network-ACL approach.
Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    excluded_handlers=["/metrics", "/api/v1/health"],
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

# API v1 routes
app.include_router(health.router, prefix="/api/v1")
app.include_router(whoami.router, prefix="/api/v1")
app.include_router(nodes.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
