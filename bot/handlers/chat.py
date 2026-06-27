from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.handlers.text_commands import process_free_text
from bot.keyboards.menus import ALL_MENU_BUTTONS
from bot.states.conversation import UserStates

router = Router()

# Состояния, где текст обрабатывают отдельные хендлеры (не свободный чат)
BLOCKED_FREE_TEXT_STATES = {
    UserStates.waiting_city.state,
    UserStates.waiting_outfit_details.state,
    UserStates.waiting_profile_field.state,
    UserStates.waiting_user_photo.state,
}


@router.message(F.text & ~F.text.in_(ALL_MENU_BUTTONS) & ~F.text.startswith("◀️"))
async def handle_free_text(
    message: Message, session: AsyncSession, state: FSMContext
) -> None:
    current_state = await state.get_state()
    if current_state in BLOCKED_FREE_TEXT_STATES:
        return

    await process_free_text(message, session, state)
