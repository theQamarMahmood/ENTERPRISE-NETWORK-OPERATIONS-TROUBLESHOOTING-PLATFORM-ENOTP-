from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import create_engine
from app.core.config import settings

is_sqlite = settings.DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}

# Async Engine (For FastAPI endpoints)
engine_kwargs = {"echo": False, "connect_args": connect_args}
if not is_sqlite:
    engine_kwargs.update({
        "pool_pre_ping": True,
        "pool_size": 20,
        "max_overflow": 10
    })

engine = create_async_engine(
    settings.DATABASE_URL,
    **engine_kwargs
)

SessionLocalAsync = async_sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)

# Sync Engine (For Celery tasks and migrations)
sync_engine_kwargs = {"echo": False, "connect_args": connect_args}
if not is_sqlite:
    sync_engine_kwargs["pool_pre_ping"] = True

sync_engine = create_engine(
    settings.SYNC_DATABASE_URL,
    **sync_engine_kwargs
)

SessionLocalSync = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Async DB Session Dependency (for async routes)"""
    async with SessionLocalAsync() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

def get_sync_db():
    """FastAPI Sync DB Session Dependency (for sync routes using db.query())"""
    db = SessionLocalSync()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
