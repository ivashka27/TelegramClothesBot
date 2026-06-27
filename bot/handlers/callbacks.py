from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.handlers.text_commands import handle_outfit_adjust
from bot.keyboards.fsm import cancel_keyboard
from bot.keyboards.menus import main_menu
from bot.services.favorites import save_favorite_from_session
from bot.services.outfit_service import send_outfit
from bot.services.wardrobe import (
    clear_wardrobe,
    format_wardrobe_list,
    get_latest_outfit_session,
    get_or_create_user,
    get_wardrobe_items,
)
from bot.states.conversation import UserStates

router = Router()

ADJUST_TEXTS = {
    "outfit:adj:casual": "Сделай образ менее официальным, более casual",
    "outfit:adj:warmer": "Сделай образ теплее, добавь более тёплые слои",
}


@router.callback_query(F.data == "outfit:regenerate")
async def cb_regenerate_outfit(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
) -> None:
    await callback.answer()
    if not callback.message:
        return
    await state.clear()
    await send_outfit(callback.message, session)


@router.callback_query(F.data == "outfit:favorite")
async def cb_favorite_outfit(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(session, telegram_id=callback.from_user.id)
    outfit = await get_latest_outfit_session(session, user.id)
    if not outfit or not outfit.selected_item_ids:
        await callback.answer("Сначала сгенерируйте образ", show_alert=True)
        return
    await save_favorite_from_session(session, user, outfit)
    await callback.answer("⭐ Образ сохранён в избранное!")


@router.callback_query(F.data.startswith("outfit:adj:"))
async def cb_adjust_outfit(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    if not callback.message:
        return
    text = ADJUST_TEXTS.get(callback.data or "")
    if text:
        await handle_outfit_adjust(callback.message, session, text)


@router.callback_query(F.data == "wardrobe:add")
async def cb_add_item(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(UserStates.waiting_add_item_photo)
    if callback.message:
        await callback.message.answer(
            "➕ Отправьте **фото вещи с подписью**.\n"
            "Или «◀️ Назад» / «🏠 В меню».",
            parse_mode="Markdown",
            reply_markup=cancel_keyboard(),
        )


@router.callback_query(F.data == "wardrobe:list")
async def cb_wardrobe_list(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    if not callback.message:
        return
    user = await get_or_create_user(session, telegram_id=callback.from_user.id)
    items = await get_wardrobe_items(session, user.id)
    await callback.message.answer(
        format_wardrobe_list(items),
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )


@router.callback_query(F.data == "wardrobe:clear:yes")
async def cb_clear_yes(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    if not callback.message:
        return
    user = await get_or_create_user(session, telegram_id=callback.from_user.id)
    count = await clear_wardrobe(session, user.id)
    await callback.message.edit_text(
        f"🧹 Гардероб очищен. Удалено вещей: {count}."
        if count
        else "Гардероб уже был пуст."
    )


@router.callback_query(F.data == "wardrobe:clear:no")
async def cb_clear_no(callback: CallbackQuery) -> None:
    await callback.answer("Отменено")
    if callback.message:
        await callback.message.edit_text("❌ Очистка гардероба отменена.")
