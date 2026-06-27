from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from bot.keyboards.menus import BTN_FAVORITES, favorites_delete_keyboard, main_menu
from bot.services.favorites import (
    EMPTY_FAVORITES_TEXT,
    delete_favorite,
    format_favorites_list,
    get_favorites,
)
from bot.services.wardrobe import get_or_create_user, get_wardrobe_items

router = Router()


async def _favorites_view(
    session: AsyncSession, user_id: int
) -> tuple[str, Optional[InlineKeyboardMarkup]]:
    favs = await get_favorites(session, user_id)
    if not favs:
        return EMPTY_FAVORITES_TEXT, None

    items = await get_wardrobe_items(session, user_id)
    items_by_id = {i.id: i.name for i in items}
    text = format_favorites_list(favs, items_by_id)
    return text, favorites_delete_keyboard(favs)


@router.message(F.text == BTN_FAVORITES)
async def show_favorites(message: Message, session: AsyncSession) -> None:
    user = await get_or_create_user(session, telegram_id=message.from_user.id)
    text, keyboard = await _favorites_view(session, user.id)

    if keyboard:
        await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=main_menu())


@router.callback_query(F.data.startswith("fav:del:"))
async def cb_delete_favorite(callback: CallbackQuery, session: AsyncSession) -> None:
    if not callback.message:
        await callback.answer()
        return

    favorite_id = int((callback.data or "").split(":")[-1])
    user = await get_or_create_user(session, telegram_id=callback.from_user.id)

    if not await delete_favorite(session, user.id, favorite_id):
        await callback.answer("Образ уже удалён", show_alert=True)
        return

    await callback.answer("Удалено из избранного")
    text, keyboard = await _favorites_view(session, user.id)

    try:
        if keyboard:
            await callback.message.edit_text(
                text, parse_mode="Markdown", reply_markup=keyboard
            )
        else:
            await callback.message.edit_text(text)
    except Exception:
        if keyboard:
            await callback.message.answer(
                text, parse_mode="Markdown", reply_markup=keyboard
            )
        else:
            await callback.message.answer(text, reply_markup=main_menu())
