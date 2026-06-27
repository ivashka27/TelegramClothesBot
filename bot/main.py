import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage

from bot.handlers import callbacks, cancel, chat, checklist, favorites, outfit, profile, start, wardrobe
from bot.middleware.db_session import DbSessionMiddleware
from bot.middleware.errors import global_error_handler
from bot.middleware.typing_action import TypingMiddleware
from bot.services.image import init_rembg_session
from config import settings
from database.session import init_db

logger = logging.getLogger(__name__)


def _normalize_proxy_url(url: str) -> str:
    # python_socks (aiogram) понимает socks5://, но не socks5h://
    if url.startswith("socks5h://"):
        return "socks5://" + url[len("socks5h://") :]
    return url


def create_bot() -> Bot:
    if settings.telegram_proxy:
        proxy = _normalize_proxy_url(settings.telegram_proxy)
        logger.info("Telegram API: подключение через прокси")
        session = AiohttpSession(proxy=proxy)
        return Bot(token=settings.bot_token, session=session)
    return Bot(token=settings.bot_token)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    settings.ensure_dirs()
    await init_db()

    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, init_rembg_session)

    bot = create_bot()
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.middleware(DbSessionMiddleware())
    dp.message.middleware(TypingMiddleware())
    dp.callback_query.middleware(DbSessionMiddleware())
    dp.callback_query.middleware(TypingMiddleware())

    dp.errors.register(global_error_handler)

    dp.include_router(cancel.router)
    dp.include_router(start.router)
    dp.include_router(checklist.router)
    dp.include_router(favorites.router)
    dp.include_router(profile.router)
    dp.include_router(outfit.router)
    dp.include_router(wardrobe.router)
    dp.include_router(callbacks.router)
    dp.include_router(chat.router)

    logger.info("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
