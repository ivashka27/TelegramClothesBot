import logging

from sqlalchemy.ext.asyncio import AsyncSession

from database.session import async_session

logger = logging.getLogger(__name__)


class DbSessionMiddleware:
    async def __call__(self, handler, event, data):
        async with async_session() as session:
            data["session"] = session
            try:
                return await handler(event, data)
            except Exception:
                await session.rollback()
                raise
