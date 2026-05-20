"""Async SQLAlchemy engine and session factory."""
from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("db")

# Create async engine. WAL mode + foreign keys set via pragma below.
engine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    future=True,
    connect_args={"check_same_thread": False},
)


# foreign_keys is a PER-CONNECTION pragma — enforce it on every new connection,
# not just the one used in init_db(). WAL is database-level so it persists once set.
@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

AsyncSessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def init_db() -> None:
    """Create tables and configure SQLite pragmas (WAL, foreign keys)."""
    log.info("db_initializing", url=settings.database_url)

    async with engine.begin() as conn:
        # Critical pragmas:
        from sqlalchemy import text
        await conn.execute(text("PRAGMA journal_mode=WAL"))
        await conn.execute(text("PRAGMA foreign_keys=ON"))
        await conn.execute(text("PRAGMA synchronous=NORMAL"))  # WAL + NORMAL = good perf

        # Import models so SQLModel.metadata picks them up
        from app.models.audit import AuditEvent  # noqa
        from app.models.node import Node  # noqa

        await conn.run_sync(SQLModel.metadata.create_all)

    log.info("db_initialized")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a DB session."""
    async with AsyncSessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
