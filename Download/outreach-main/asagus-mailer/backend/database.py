"""
Async SQLAlchemy engine + session factory for SQLite with WAL mode.
Database auto-creates all tables on first startup.
"""

from pathlib import Path
import shutil

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
ROOT_DB_PATH = (ROOT_DIR / "asagus.db").resolve()
BACKEND_DB_PATH = (BASE_DIR / "asagus.db").resolve()

# Keep data consistent regardless of CWD by using the repo-root DB.
# If an older backend-local DB exists and root DB is missing/empty, migrate it.
if BACKEND_DB_PATH.exists():
    try:
        if (not ROOT_DB_PATH.exists()) or ROOT_DB_PATH.stat().st_size < 4096:
            shutil.copy2(BACKEND_DB_PATH, ROOT_DB_PATH)
    except Exception:
        pass

DATABASE_URL = f"sqlite+aiosqlite:///{ROOT_DB_PATH.as_posix()}"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    """Dependency to get DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Create all tables and configure WAL mode."""
    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA journal_mode=WAL;"))
        await conn.execute(text("PRAGMA foreign_keys=ON;"))
        # Lightweight schema migration for new columns
        try:
            result = await conn.execute(text("PRAGMA table_info(sender_accounts);"))
            cols = {row[1] for row in result.fetchall()}
            if "auth_type" not in cols:
                await conn.execute(text("ALTER TABLE sender_accounts ADD COLUMN auth_type VARCHAR DEFAULT 'smtp';"))
        except Exception:
            pass
        from models import Base as ModelBase
        await conn.run_sync(ModelBase.metadata.create_all)
