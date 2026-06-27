from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.menus import BTN_CHECKLIST, main_menu
from bot.services.checklist import format_setup_checklist
from bot.services.wardrobe import get_or_create_user, get_wardrobe_items

router = Router()


@router.message(F.text == BTN_CHECKLIST)
async def show_checklist(message: Message, session: AsyncSession) -> None:
    user = await get_or_create_user(session, telegram_id=message.from_user.id)
    items = await get_wardrobe_items(session, user.id)
    await message.answer(
        format_setup_checklist(user, items),
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )
