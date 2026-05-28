"""Structured JSON logging — same format the controller uses, so Promtail's
existing pipeline ingests node-agent logs uniformly."""
import logging
import sys

import structlog

from app.config import settings


def configure() -> None:
    logging.basicConfig(
        stream=sys.stdout,
        level=settings.log_level.upper(),
        format="%(message)s",
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging._nameToLevel[settings.log_level.upper()]
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
