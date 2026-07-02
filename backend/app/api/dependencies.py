import asyncpg
from app.core.config import settings

pool = None

async def get_db_pool():
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=2,
            max_size=10,
        )
    return pool

async def get_db():
    p = await get_db_pool()
    async with p.acquire() as conn:
        yield conn

async def close_db():
    global pool
    if pool:
        await pool.close()
        pool = None
