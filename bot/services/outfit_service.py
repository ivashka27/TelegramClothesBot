from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

from aiogram.types import FSInputFile, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.menus import outfit_actions_keyboard, main_menu
from bot.services.ai import generate_outfit
from bot.services.appearance import build_outfit_preview_prompt_local, user_has_saved_photo
from bot.services.wardrobe import (
    create_outfit_session,
    get_or_create_user,
    get_wardrobe_items,
)
from bot.services.weather import fetch_weather
from bot.services.yandex_art import generate_outfit_preview, preview_error_message

logger = logging.getLogger(__name__)


async def _send_preview(message: Message, user, selected, preview_status_msg) -> None:
    outfit_desc = "\n".join(
        f"- {item.name}" + (f" ({item.category})" if item.category else "")
        for item in selected
    )
    try:
        prompt = build_outfit_preview_prompt_local(user, outfit_desc)
        preview = await generate_outfit_preview(prompt)
        if preview.image:
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp.write(preview.image)
                tmp_path = tmp.name
            await preview_status_msg.delete()
            await message.answer_photo(
                FSInputFile(tmp_path),
                caption="🪞 Примерка образа",
            )
            Path(tmp_path).unlink(missing_ok=True)
        else:
            has_photo = bool(user.reference_photo_path or user.appearance_description)
            await preview_status_msg.edit_text(
                preview_error_message(preview.error, has_photo)
            )
    except Exception:
        logger.exception("Outfit preview generation failed")
        await preview_status_msg.edit_text(
            "🎨 Примерка пропущена — образ и советы уже готовы."
        )


async def _deliver_outfit(
    message: Message,
    session: AsyncSession,
    user,
    items,
    weather_text: str,
    result,
    destination: str | None,
    wishes: str | None,
    *,
    header: str = "👔 **Образ:**",
    with_actions: bool = True,
    with_preview: bool = True,
    show_main_menu: bool = True,
) -> None:
    session_response = result.explanation
    if result.item_tips:
        session_response += f"\n\n👟 **Советы по вещам:**\n{result.item_tips}"
    if result.advice:
        session_response += f"\n\n💡 **Общий совет:**\n{result.advice}"

    await create_outfit_session(
        session,
        user_id=user.id,
        weather_data=json.dumps({"raw": weather_text}, ensure_ascii=False),
        item_ids=result.item_ids,
        ai_response=session_response,
        destination=destination,
        wishes=wishes,
    )

    selected = [i for i in items if i.id in result.item_ids]

    await message.answer(
        f"🌤 **Погода:**\n{weather_text}\n\n{header}\n{result.explanation}",
        parse_mode="Markdown",
    )

    for item in selected:
        if item.processed_image_path:
            await message.answer_photo(
                FSInputFile(item.processed_image_path),
                caption=item.name,
            )

    if result.item_tips:
        await message.answer(
            f"👟 **Советы по каждой вещи:**\n{result.item_tips}",
            parse_mode="Markdown",
        )
    if result.advice:
        await message.answer(
            f"💡 **Общий совет:**\n{result.advice}",
            parse_mode="Markdown",
        )

    if with_preview:
        if user_has_saved_photo(user):
            preview_status = await message.answer("🎨 Генерирую примерку образа на вас...")
            await _send_preview(message, user, selected, preview_status)
        else:
            await message.answer(
                "📸 **Примерка недоступна** — загрузите своё фото через «📸 Моё фото».",
                parse_mode="Markdown",
            )

    footer = (
        "Напишите комментарий — поправлю образ.\n"
        "Или используйте кнопки ниже 👇"
        if with_actions
        else ""
    )
    if with_actions and footer:
        await message.answer(footer, reply_markup=outfit_actions_keyboard())
    if show_main_menu:
        await message.answer("Меню команд:", reply_markup=main_menu())


async def send_outfit(
    message: Message,
    session: AsyncSession,
    destination: str | None = None,
    wishes: str | None = None,
) -> None:
    user = await get_or_create_user(session, telegram_id=message.from_user.id)
    if not user.city:
        await message.answer(
            "Сначала укажите город — без него не смогу учесть погоду.\n"
            "Нажмите «📍 Указать город» или «📋 Что настроить»."
        )
        return

    items = await get_wardrobe_items(session, user.id)
    if not items:
        await message.answer(
            "Гардероб пуст. Нажмите «➕ Добавить вещь» и отправьте фото с подписью."
        )
        return

    status = await message.answer("⏳ Смотрю погоду и подбираю образ...")

    try:
        weather = await fetch_weather(user.city)
        weather_text = weather.to_text()
        result = await generate_outfit(items, weather_text, destination, wishes)

        if not result.item_ids:
            await status.edit_text(result.explanation)
            return

        await status.delete()
        await _deliver_outfit(
            message, session, user, items, weather_text, result, destination, wishes
        )
    except Exception:
        logger.exception("Outfit generation failed")
        await status.edit_text(
            "❌ Не удалось подобрать образ. Попробуйте ещё раз или нажмите «📋 Что настроить»."
        )


async def send_two_outfits(
    message: Message,
    session: AsyncSession,
    destination: str | None = None,
    base_wishes: str | None = None,
) -> None:
    user = await get_or_create_user(session, telegram_id=message.from_user.id)
    if not user.city:
        await message.answer("📍 Сначала укажите город.")
        return
    items = await get_wardrobe_items(session, user.id)
    if not items:
        await message.answer("Сначала добавьте вещи в гардероб.")
        return

    status = await message.answer("⏳ Подбираю два варианта образа...")
    try:
        weather = await fetch_weather(user.city)
        weather_text = weather.to_text()

        casual = await generate_outfit(
            items,
            weather_text,
            destination,
            f"{base_wishes or ''} casual, расслабленный стиль".strip(),
        )
        formal = await generate_outfit(
            items,
            weather_text,
            destination,
            f"{base_wishes or ''} более строгий, аккуратный стиль".strip(),
        )

        await status.delete()

        if casual.item_ids:
            await _deliver_outfit(
                message,
                session,
                user,
                items,
                weather_text,
                casual,
                destination,
                base_wishes,
                header="👔 **Вариант 1 — casual:**",
                with_actions=False,
                with_preview=False,
                show_main_menu=False,
            )
        if formal.item_ids:
            await _deliver_outfit(
                message,
                session,
                user,
                items,
                weather_text,
                formal,
                destination,
                base_wishes,
                header="👔 **Вариант 2 — строже:**",
                with_actions=True,
                with_preview=True,
            )
        if not casual.item_ids and not formal.item_ids:
            await message.answer("Не удалось подобрать варианты. Попробуйте позже.")
    except Exception:
        logger.exception("Two outfits generation failed")
        await status.edit_text("❌ Не удалось подобрать два варианта. Попробуйте позже.")
