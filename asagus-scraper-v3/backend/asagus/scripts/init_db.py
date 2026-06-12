from __future__ import annotations

import asyncio
from pathlib import Path

import asyncpg

from asagus.config import get_settings


async def main() -> None:
    settings = get_settings()
    schema_path = Path(__file__).resolve().parents[1] / "db" / "schema.sql"
    sql = schema_path.read_text(encoding="utf-8")
    conn = await asyncpg.connect(settings.postgres_url)
    try:
        await conn.execute(sql)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
