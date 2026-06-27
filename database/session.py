from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import settings
from database.models import Base

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

USER_MIGRATIONS = [
    "ALTER TABLE users ADD COLUMN gender VARCHAR(20)",
    "ALTER TABLE users ADD COLUMN height_cm INTEGER",
    "ALTER TABLE users ADD COLUMN weight_kg FLOAT",
    "ALTER TABLE users ADD COLUMN shoe_size VARCHAR(20)",
    "ALTER TABLE users ADD COLUMN clothing_size VARCHAR(20)",
    "ALTER TABLE users ADD COLUMN age INTEGER",
    "ALTER TABLE users ADD COLUMN body_type VARCHAR(50)",
    "ALTER TABLE users ADD COLUMN reference_photo_path VARCHAR(512)",
    "ALTER TABLE users ADD COLUMN appearance_description TEXT",
]


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for stmt in USER_MIGRATIONS:
            try:
                await conn.execute(text(stmt))
            except Exception:
                pass


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
