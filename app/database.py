import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import settings

# Supabase's transaction pooler (port 6543) runs pgbouncer in transaction mode,
# which does NOT support prepared statements. asyncpg uses them by default, so:
#   - statement_cache_size=0 disables asyncpg's statement cache
#   - a unique prepared_statement_name_func avoids name collisions across pooled conns
#   - NullPool: let pgbouncer handle pooling, not SQLAlchemy
_is_supabase_pooler = (
    "+asyncpg" in settings.database_url and "pooler.supabase.com" in settings.database_url
)

_engine_kwargs: dict = {"pool_pre_ping": True}
if _is_supabase_pooler:
    _engine_kwargs = {
        "poolclass": NullPool,
        "connect_args": {
            "statement_cache_size": 0,
            "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4()}__",
        },
    }

engine = create_async_engine(settings.database_url, **_engine_kwargs)
async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session
