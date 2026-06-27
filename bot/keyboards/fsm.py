from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from bot.keyboards.menus import BTN_BACK, BTN_MAIN_MENU


def nav_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_BACK), KeyboardButton(text=BTN_MAIN_MENU)]],
        resize_keyboard=True,
    )


def cancel_keyboard() -> ReplyKeyboardMarkup:
    """Для совместимости — то же, что nav_keyboard."""
    return nav_keyboard()
