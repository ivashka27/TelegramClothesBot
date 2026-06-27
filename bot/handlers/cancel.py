from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.menus import BTN_BACK, BTN_CANCEL, BTN_MAIN_MENU, main_menu
from bot.states.conversation import UserStates

router = Router()

CANCEL_ALIASES = {BTN_CANCEL.lower(), "отмена", "cancel"}


@router.message(F.text == BTN_MAIN_MENU)
async def go_main_menu(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    await state.clear()
    if current:
        await message.answer("🏠 Главное меню:", reply_markup=main_menu())
    else:
        await message.answer("Вы уже в главном меню.", reply_markup=main_menu())


@router.message(F.text == BTN_BACK)
async def go_back(message: Message, state: FSMContext, session: AsyncSession) -> None:
    current = await state.get_state()
    if current == UserStates.waiting_profile_field.state:
        await state.clear()
        from bot.handlers.profile import show_profile

        await show_profile(message, session, state)
        return

    await state.clear()
    if current:
        await message.answer("✅ Шаг отменён.", reply_markup=main_menu())
    else:
        await message.answer("Вы уже в главном меню.", reply_markup=main_menu())


@router.message(F.text.func(lambda t: t and t.strip().lower() in CANCEL_ALIASES))
async def cancel_alias(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("✅ Отменено.", reply_markup=main_menu())
