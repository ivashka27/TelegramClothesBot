from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.enums import ChatAction
from aiogram.types import Message, TelegramObject


class TypingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.chat:
            try:
                await event.bot.send_chat_action(event.chat.id, ChatAction.TYPING)
            except Exception:
                pass
        return await handler(event, data)
