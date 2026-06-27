from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, KeyboardButton, Message, ReplyKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.fsm import cancel_keyboard
from bot.keyboards.menus import (
    BTN_EDIT_PROFILE,
    BTN_MAIN_MENU,
    BTN_PROFILE,
    BTN_USER_PHOTO,
    main_menu,
    user_photo_actions_keyboard,
)
from bot.services.appearance import delete_user_photo, user_has_saved_photo
from bot.services.profile import (
    apply_profile_field,
    format_user_profile,
    parse_profile_update,
)
from bot.services.wardrobe import get_or_create_user
from bot.states.conversation import UserStates

router = Router()

PROFILE_FIELDS_HINT = (
    "✏️ **Изменение параметров**\n\n"
    "Напишите параметр и значение, например:\n"
    "• `пол женский`\n"
    "• `рост 168`\n"
    "• `вес 62`\n"
    "• `размер обуви 39`\n"
    "• `размер одежды M`\n"
    "• `возраст 28`\n"
    "• `телосложение стройное`\n\n"
    "Можно несколько через запятую: `рост 175, вес 70`"
)

UPLOAD_PHOTO_HINT = (
    "📸 **Загрузка фото для примерки**\n\n"
    "Отправьте своё фото в полный рост или по пояс.\n"
    "Использую его при генерации примерки образов.\n\n"
    "◀️ Назад или 🏠 В меню — выйти."
)


@router.message(F.text == BTN_PROFILE)
async def show_profile(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    user = await get_or_create_user(session, telegram_id=message.from_user.id)
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_EDIT_PROFILE), KeyboardButton(text=BTN_USER_PHOTO)],
            [KeyboardButton(text=BTN_MAIN_MENU)],
        ],
        resize_keyboard=True,
    )
    await message.answer(format_user_profile(user), parse_mode="Markdown", reply_markup=kb)


@router.message(F.text == BTN_EDIT_PROFILE)
async def edit_profile_hint(message: Message, state: FSMContext) -> None:
    await state.set_state(UserStates.waiting_profile_field)
    await message.answer(
        PROFILE_FIELDS_HINT + "\n\n◀️ Назад или 🏠 В меню — выйти.",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard(),
    )


@router.message(F.text == BTN_USER_PHOTO)
async def request_user_photo(
    message: Message, session: AsyncSession, state: FSMContext
) -> None:
    user = await get_or_create_user(session, telegram_id=message.from_user.id)

    if user_has_saved_photo(user):
        await state.clear()
        caption = "📸 **Ваше фото** для примерки образов."
        if user.appearance_description:
            caption += f"\n\n**AI-описание:**\n{user.appearance_description}"
        await message.answer_photo(
            FSInputFile(user.reference_photo_path),
            caption=caption,
            parse_mode="Markdown",
            reply_markup=user_photo_actions_keyboard(),
        )
        return

    await state.set_state(UserStates.waiting_user_photo)
    await message.answer(
        UPLOAD_PHOTO_HINT,
        parse_mode="Markdown",
        reply_markup=cancel_keyboard(),
    )


@router.callback_query(F.data == "user_photo:replace")
async def cb_user_photo_replace(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(UserStates.waiting_user_photo)
    if callback.message:
        await callback.message.answer(
            UPLOAD_PHOTO_HINT,
            parse_mode="Markdown",
            reply_markup=cancel_keyboard(),
        )


@router.callback_query(F.data == "user_photo:delete")
async def cb_user_photo_delete(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
) -> None:
    user = await get_or_create_user(session, telegram_id=callback.from_user.id)
    if not user_has_saved_photo(user):
        await callback.answer("Фото уже удалено", show_alert=True)
        return

    delete_user_photo(user)
    await session.commit()
    await state.clear()
    await callback.answer("Фото удалено")

    if callback.message:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(
            "✅ Фото удалено.\n\n"
            "Примерка образов отключена, пока не загрузите новое фото через «📸 Моё фото».",
            reply_markup=main_menu(),
        )


@router.message(UserStates.waiting_profile_field)
async def profile_field_received(
    message: Message, session: AsyncSession, state: FSMContext
) -> None:
    user = await get_or_create_user(session, telegram_id=message.from_user.id)
    updates = parse_profile_update(message.text or "")
    if not updates:
        await message.answer(
            "Не понял параметр. Пример: «рост 175» или «пол мужской»."
        )
        return

    errors = []
    for field, value in updates:
        err = apply_profile_field(user, field, value)
        if err:
            errors.append(err)

    await session.commit()
    await state.clear()

    if errors:
        await message.answer("\n".join(errors))
    await message.answer(format_user_profile(user), parse_mode="Markdown", reply_markup=main_menu())


async def apply_profile_from_text(
    message: Message, session: AsyncSession, text: str
) -> bool:
    """Применяет параметры профиля из свободного текста. Возвращает True если что-то обновлено."""
    updates = parse_profile_update(text)
    if not updates:
        return False
    user = await get_or_create_user(session, telegram_id=message.from_user.id)
    for field, value in updates:
        apply_profile_field(user, field, value)
    await session.commit()
    await message.answer(
        "✅ Профиль обновлён.\n\n" + format_user_profile(user),
        parse_mode="Markdown",
    )
    return True
