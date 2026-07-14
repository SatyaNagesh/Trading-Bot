"""Connection pooling and database health management."""

from packages.core.database import engine, async_session, check_health
from packages.core.logging import get_logger
from packages.hardening.protection import ConnectionPool

logger = get_logger("connection_manager")

db_pool = ConnectionPool(min_size=5, max_size=20)


async def acquire_connection(name: str = "default") -> str:
    conn_id = db_pool.acquire(name)
    logger.debug("connection_acquired", id=conn_id, name=name)
    return conn_id


def release_connection(conn_id: str) -> None:
    db_pool.release(conn_id)


async def full_health_check() -> dict:
    db_ok = await check_health()
    return {
        "database": db_ok,
        "pool_active": db_pool.active_count,
        "pool_min": db_pool.min_size,
        "pool_max": db_pool.max_size,
    }
