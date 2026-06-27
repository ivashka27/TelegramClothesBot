from __future__ import annotations

import asyncio
import logging
from io import BytesIO

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.fsm import cancel_keyboard
from bot.keyboards.menus import (
    BTN_ADD_ITEM,
    BTN_CLEAR_WARDROBE,
    BTN_DELETE_ITEMS,
    BTN_VIEW_PHOTOS,
    BTN_WARDROBE,
    after_add_item_keyboard,
    clear_wardrobe_confirm_keyboard,
    main_menu,
)
from bot.services.ai import (
    extract_item_info,
    match_items_for_deletion,
    match_items_for_viewing,
)
from bot.services.formatting import format_items_expandable_list
from bot.services.image import remove_background, save_wardrobe_images
from bot.services.wardrobe import (
    add_wardrobe_item,
    delete_wardrobe_items,
    format_wardrobe_list,
    get_or_create_user,
    get_wardrobe_items,
    match_items_by_names,
)
from bot.states.conversation import UserStates

logger = logging.getLogger(__name__)

router = Router()


@router.message(F.text == BTN_WARDROBE)
async def show_wardrobe(message: Message, session: AsyncSession) -> None:
    user = await get_or_create_user(session, telegram_id=message.from_user.id)
    items = await get_wardrobe_items(session, user.id)
    await message.answer(format_wardrobe_list(items), parse_mode="Markdown")


@router.message(F.text == BTN_ADD_ITEM)
async def btn_add_item(message: Message, state: FSMContext) -> None:
    await state.set_state(UserStates.waiting_add_item_photo)
    await message.answer(
        "➕ Отправьте **фото вещи с подписью** — что это за предмет.\n"
        "Например: «Белая футболка, хлопок»\n\n"
        "⏳ Первое фото может обрабатываться 1–2 мин (удаление фона).\n"
        "◀️ Назад или 🏠 В меню — выйти.",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard(),
    )


@router.message(F.text == BTN_VIEW_PHOTOS)
async def btn_view_photos(
    message: Message, session: AsyncSession, state: FSMContext
) -> None:
    user = await get_or_create_user(session, telegram_id=message.from_user.id)
    items = await get_wardrobe_items(session, user.id)
    if not items:
        await message.answer("Гардероб пуст.")
        return
    await state.set_state(UserStates.waiting_view_items)
    text = format_items_expandable_list(
        items,
        "👁 **Ваши вещи** — раскройте список:",
        "Перечислите названия через запятую.\n"
        "Или текстом: «покажи белую футболку»\n"
        "◀️ Назад или 🏠 В меню — выйти.",
    )
    await message.answer(text, parse_mode="HTML", reply_markup=cancel_keyboard())


@router.message(F.text == BTN_DELETE_ITEMS)
async def btn_delete_items(
    message: Message, session: AsyncSession, state: FSMContext
) -> None:
    user = await get_or_create_user(session, telegram_id=message.from_user.id)
    items = await get_wardrobe_items(session, user.id)
    if not items:
        await message.answer("Гардероб пуст — удалять нечего.")
        return
    await state.set_state(UserStates.waiting_delete_items)
    text = format_items_expandable_list(
        items,
        "🗑 **Выберите вещи для удаления:**",
        "Перечислите названия через запятую.\n"
        "Или текстом: «удали чёрную футболку»\n"
        "◀️ Назад или 🏠 В меню — выйти.",
    )
    await message.answer(text, parse_mode="HTML", reply_markup=cancel_keyboard())


@router.message(F.text == BTN_CLEAR_WARDROBE)
async def btn_clear_wardrobe(message: Message, session: AsyncSession) -> None:
    user = await get_or_create_user(session, telegram_id=message.from_user.id)
    items = await get_wardrobe_items(session, user.id)
    if not items:
        await message.answer("Гардероб уже пуст.")
        return
    await message.answer(
        f"⚠️ Удалить **все {len(items)} вещ(и/ей)** из гардероба?\n"
        "Это действие нельзя отменить.",
        parse_mode="Markdown",
        reply_markup=clear_wardrobe_confirm_keyboard(),
    )


@router.message(UserStates.waiting_view_items)
async def view_items_by_names(
    message: Message, session: AsyncSession, state: FSMContext
) -> None:
    await state.clear()
    await _send_item_photos(message, session, message.text or "", by_names=True)


@router.message(UserStates.waiting_add_item_photo, F.text)
async def add_item_waiting_text(
    message: Message, session: AsyncSession, state: FSMContext
) -> None:
    from bot.handlers.text_commands import process_free_text

    await state.clear()
    await process_free_text(message, session, state)


@router.message(UserStates.waiting_delete_items)
async def delete_items_by_names(
    message: Message, session: AsyncSession, state: FSMContext
) -> None:
    await state.clear()
    text = message.text or ""
    lower = text.lower()
    if any(w in lower for w in ("удали", "убери", "выкини", "delete", "удалить")):
        await handle_delete_items(message, session, text, [])
        return

    user = await get_or_create_user(session, telegram_id=message.from_user.id)
    items = await get_wardrobe_items(session, user.id)
    to_delete = match_items_by_names(items, text)
    if not to_delete:
        await message.answer(
            "Не нашёл вещи с такими названиями. Проверьте написание или откройте «👗 Мой гардероб»."
        )
        return
    names = await delete_wardrobe_items(session, to_delete)
    await message.answer(
        f"🗑 Удалено ({len(names)}):\n" + "\n".join(f"• {n}" for n in names)
    )


@router.message(F.photo)
async def handle_photo(message: Message, session: AsyncSession, state: FSMContext) -> None:
    current = await state.get_state()

    if current == UserStates.waiting_user_photo.state:
        await _handle_user_photo(message, session, state)
        return

    caption = message.caption or ""
    if current == UserStates.waiting_add_item_photo.state or caption.strip():
        await state.clear()
        await _add_wardrobe_photo(message, session)
        return

    await message.answer(
        "Чтобы добавить вещь — нажмите «➕ Добавить вещь».\n"
        "Для фото профиля — «📸 Моё фото»."
    )


async def _handle_user_photo(
    message: Message, session: AsyncSession, state: FSMContext
) -> None:
    from bot.keyboards.menus import user_photo_actions_keyboard
    from bot.services.appearance import analyze_user_photo, save_user_photo

    await state.clear()
    status = await message.answer("⏳ Анализирую фото...")

    try:
        photo = message.photo[-1]
        file = await message.bot.get_file(photo.file_id)
        buffer = BytesIO()
        await message.bot.download_file(file.file_path, buffer)
        image_bytes = buffer.getvalue()

        user = await get_or_create_user(session, telegram_id=message.from_user.id)
        path = save_user_photo(user.telegram_id, image_bytes)
        description = await analyze_user_photo(image_bytes)

        user.reference_photo_path = path
        user.appearance_description = description
        await session.commit()

        await status.delete()
        await message.answer_photo(
            FSInputFile(path),
            caption=(
                "✅ Фото сохранено для примерки образов.\n\n"
                f"**AI-описание:**\n{description}"
            ),
            parse_mode="Markdown",
            reply_markup=user_photo_actions_keyboard(),
        )
    except Exception:
        logger.exception("User photo analysis failed")
        await status.edit_text(
            "❌ Не удалось обработить фото. Попробуйте другое изображение."
        )


async def _add_wardrobe_photo(message: Message, session: AsyncSession) -> None:
    user = await get_or_create_user(
        session,
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )
    caption = message.caption or ""
    if not caption.strip():
        await message.answer(
            "Добавьте подпись к фото — что это за вещь.\n"
            "Например: «Чёрная кожаная куртка»"
        )
        return

    status = await message.answer("⏳ Скачиваю фото и удаляю фон...")

    try:
        photo = message.photo[-1]
        file = await message.bot.get_file(photo.file_id)
        buffer = BytesIO()
        await message.bot.download_file(file.file_path, buffer)
        original_bytes = buffer.getvalue()

        loop = asyncio.get_running_loop()
        processed_bytes = await loop.run_in_executor(
            None, remove_background, original_bytes
        )

        name, category, description = await extract_item_info(caption)

        item = await add_wardrobe_item(
            session,
            user_id=user.id,
            name=name,
            original_path="",
            processed_path="",
            category=category,
            description=description,
        )

        original_path, processed_path = save_wardrobe_images(
            user.telegram_id, item.id, original_bytes, processed_bytes
        )
        item.original_image_path = original_path
        item.processed_image_path = processed_path
        await session.commit()

        cat_text = f" ({category})" if category else ""
        await status.delete()
        await message.answer_photo(
            FSInputFile(processed_path),
            caption=f"✅ Добавлено: **{name}**{cat_text}",
            parse_mode="Markdown",
            reply_markup=after_add_item_keyboard(),
        )
    except Exception:
        logger.exception("Failed to process wardrobe photo")
        await status.edit_text(
            "❌ Не удалось обработать фото. Попробуйте другое фото или подпись."
        )


async def _send_item_photos(
    message: Message,
    session: AsyncSession,
    query: str,
    by_names: bool = False,
) -> None:
    user = await get_or_create_user(session, telegram_id=message.from_user.id)
    items = await get_wardrobe_items(session, user.id)
    if not items:
        await message.answer("Гардероб пуст.")
        return

    if by_names:
        matched = match_items_by_names(items, query)
    else:
        matched = await match_items_for_viewing(items, query)

    if not matched:
        await message.answer("Не нашёл подходящих вещей. Уточните запрос.")
        return

    await message.answer(f"Нашёл {len(matched)} вещ(и/ей):")
    for item in matched:
        if item.processed_image_path:
            await message.answer_photo(
                FSInputFile(item.processed_image_path),
                caption=item.name,
            )


async def handle_list_wardrobe(message: Message, session: AsyncSession) -> None:
    user = await get_or_create_user(session, telegram_id=message.from_user.id)
    items = await get_wardrobe_items(session, user.id)
    await message.answer(format_wardrobe_list(items), parse_mode="Markdown")


async def handle_view_items(message: Message, session: AsyncSession, query: str) -> None:
    await _send_item_photos(message, session, query, by_names=False)


async def handle_delete_items(
    message: Message, session: AsyncSession, query: str, item_names: list[str]
) -> None:
    user = await get_or_create_user(session, telegram_id=message.from_user.id)
    items = await get_wardrobe_items(session, user.id)
    if not items:
        await message.answer("Гардероб пуст — удалять нечего.")
        return

    status = await message.answer("⏳ Ищу вещи для удаления...")
    search_query = ", ".join(item_names) if item_names else query

    try:
        to_delete = await match_items_for_deletion(items, search_query)
        if not to_delete:
            await status.edit_text(
                "Не нашёл подходящих вещей для удаления. "
                "Попробуйте «🗑 Удалить вещи» или назовите точнее."
            )
            return

        names = await delete_wardrobe_items(session, to_delete)
        await status.edit_text(
            f"🗑 Удалено ({len(names)}):\n" + "\n".join(f"• {n}" for n in names)
        )
    except Exception:
        logger.exception("Delete items failed")
        await status.edit_text("❌ Не удалось удалить вещи. Попробуйте ещё раз.")


async def handle_clear_wardrobe(message: Message, session: AsyncSession) -> None:
    user = await get_or_create_user(session, telegram_id=message.from_user.id)
    items = await get_wardrobe_items(session, user.id)
    if not items:
        await message.answer("Гардероб уже пуст.")
        return
    await message.answer(
        f"⚠️ Удалить **все {len(items)} вещ(и/ей)**?\n"
        "Подтвердите кнопками ниже.",
        parse_mode="Markdown",
        reply_markup=clear_wardrobe_confirm_keyboard(),
    )
