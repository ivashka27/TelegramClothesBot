from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.menus import BTN_HELP, main_menu
from bot.services.checklist import format_setup_checklist
from bot.services.wardrobe import get_or_create_user, get_wardrobe_items

router = Router()

HELP_TEXT = (
    "**С чего начать:**\n"
    "0. 📍 Город — для погоды\n"
    "1. 👤 Профиль — пол, рост, размеры\n"
    "2. 📸 Моё фото — для примерки (необязательно)\n"
    "3. ➕ 3–5 вещей — фото с подписью\n"
    "4. ✨ Сгенерировать наряд\n\n"
    "**Гардероб:**\n"
    "➕ Добавить вещь — фото с подписью (первое фото может обрабатываться 1–2 мин)\n"
    "👁 Посмотреть фото — список → названия через запятую\n"
    "   _Или текстом:_ «покажи белую футболку»\n"
    "🗑 Удалить вещи — список → названия\n"
    "   _Или текстом:_ «удали старые кроссовки»\n"
    "🧹 Очистить гардероб — с подтверждением\n"
    "👗 Мой гардероб — текстовый список\n\n"
    "**Образы:**\n"
    "✨ Сгенерировать — погода + фото вещей + советы + примерка\n"
    "👔 Два варианта — casual и более строгий\n"
    "📅 План на неделю — 5 образов с учётом прогноза\n"
    "🛒 Чего не хватает — что докупить к гардеробу\n"
    "⭐ Избранные — сохранённые образы\n\n"
    "**После генерации образа** можно написать комментарий "
    "или нажать кнопки под сообщением.\n\n"
    "❌ **Отмена** — в любой момент, когда бот ждёт ввод\n"
    "📋 **Что настроить** — чеклист готовности"
)


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    user = await get_or_create_user(
        session,
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )
    items = await get_wardrobe_items(session, user.id)
    checklist = format_setup_checklist(user, items)
    await message.answer(
        f"Привет, {message.from_user.first_name or 'друг'}! 👋\n\n"
        "Я помогу собрать образ из вашего гардероба с учётом погоды и ваших параметров.\n\n"
        f"{checklist}",
        reply_markup=main_menu(),
        parse_mode="Markdown",
    )


@router.message(F.text == BTN_HELP)
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, parse_mode="Markdown")
