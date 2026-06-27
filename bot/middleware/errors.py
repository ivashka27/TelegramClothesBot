import logging

from aiogram import Bot
from aiogram.types import ErrorEvent

from bot.keyboards.menus import main_menu

logger = logging.getLogger(__name__)

USER_ERROR_TEXT = (
    "😔 Что-то пошло не так на моей стороне.\n\n"
    "Попробуйте ещё раз или нажмите /start.\n"
    "Если не помогло — «❓ Помощь»."
)


async def global_error_handler(event: ErrorEvent, bot: Bot) -> bool:
    logger.exception(
        "Unhandled error processing update %s",
        event.update.update_id if event.update else "?",
        exc_info=event.exception,
    )

    chat_id = None
    if event.update.message:
        chat_id = event.update.message.chat.id
    elif event.update.callback_query and event.update.callback_query.message:
        chat_id = event.update.callback_query.message.chat.id

    if chat_id:
        try:
            await bot.send_message(chat_id, USER_ERROR_TEXT, reply_markup=main_menu())
        except Exception:
            logger.exception("Failed to send error message to user")
    return True
