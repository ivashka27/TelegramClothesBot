from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.handlers.profile import apply_profile_from_text
from bot.handlers.wardrobe import (
    handle_clear_wardrobe,
    handle_delete_items,
    handle_list_wardrobe,
    handle_view_items,
)
from bot.services.ai import IntentAction, adjust_outfit, parse_user_intent
from bot.services.outfit_service import send_outfit
from bot.services.wardrobe import (
    get_latest_outfit_session,
    get_or_create_user,
    get_wardrobe_items,
    parse_item_ids,
    set_user_city,
    update_outfit_session,
)
from bot.services.weather import WeatherError, fetch_weather


async def handle_outfit_adjust(
    message: Message, session: AsyncSession, text: str
) -> None:
    user = await get_or_create_user(session, telegram_id=message.from_user.id)
    latest_outfit = await get_latest_outfit_session(session, user.id)
    if not latest_outfit:
        await message.answer(
            "Сначала сгенерируйте образ — «✨ Сгенерировать наряд на сегодня»."
        )
        return
    if not user.city:
        await message.answer("Укажите город для учёта погоды.")
        return

    items = await get_wardrobe_items(session, user.id)
    current_ids = parse_item_ids(latest_outfit.selected_item_ids)
    status = await message.answer("⏳ Думаю над вашим комментарием...")

    try:
        weather = await fetch_weather(user.city)
        result = await adjust_outfit(
            items,
            current_ids,
            weather.to_text(),
            text,
            latest_outfit.ai_response or "",
        )
        await update_outfit_session(
            session, latest_outfit, result.item_ids, result.explanation, text
        )
        response = result.explanation
        if result.item_tips:
            response += f"\n\n👟 {result.item_tips}"
        if result.advice:
            response += f"\n\n💡 {result.advice}"

        await status.delete()
        await message.answer(response, parse_mode="Markdown")

        if result.item_ids != current_ids:
            selected = [i for i in items if i.id in result.item_ids]
            for item in selected:
                if item.processed_image_path:
                    await message.answer_photo(
                        FSInputFile(item.processed_image_path),
                        caption=item.name,
                    )
    except Exception:
        await status.edit_text("❌ Не удалось обновить образ. Попробуйте ещё раз.")


async def process_free_text(
    message: Message, session: AsyncSession, state: FSMContext
) -> None:
    text = (message.text or "").strip()
    if not text:
        return

    if await apply_profile_from_text(message, session, text):
        return

    user = await get_or_create_user(session, telegram_id=message.from_user.id)
    latest_outfit = await get_latest_outfit_session(session, user.id)
    has_active_outfit = latest_outfit is not None

    intent = await parse_user_intent(text, has_active_outfit)

    if intent.action == IntentAction.UNSUPPORTED:
        await message.answer(
            intent.message or "Такой функционал пока не поддерживается."
        )
        return

    if intent.action == IntentAction.UNKNOWN:
        await message.answer(
            intent.message
            or "Не совсем понял запрос. Попробуйте иначе или нажмите «❓ Помощь»."
        )
        return

    if intent.action == IntentAction.LIST_WARDROBE:
        await handle_list_wardrobe(message, session)
        return

    if intent.action == IntentAction.VIEW_ITEM:
        await handle_view_items(message, session, text)
        return

    if intent.action == IntentAction.DELETE_ITEM:
        await handle_delete_items(message, session, text, intent.item_names)
        return

    if intent.action == IntentAction.CLEAR_WARDROBE:
        await handle_clear_wardrobe(message, session)
        return

    if intent.action == IntentAction.SET_PROFILE:
        if not await apply_profile_from_text(message, session, text):
            await message.answer(
                "Не понял параметры профиля. Пример: «рост 175, вес 70»\n"
                "Или откройте «👤 Мой профиль»."
            )
        return

    if intent.action == IntentAction.SET_CITY:
        city = text
        for prefix in ("город ", "я в ", "я из ", "живу в "):
            if city.lower().startswith(prefix):
                city = city[len(prefix) :].strip()
        try:
            weather = await fetch_weather(city)
            await set_user_city(session, user, weather.city)
            await message.answer(
                f"✅ Город: **{weather.city}**\n{weather.to_text()}",
                parse_mode="Markdown",
            )
        except WeatherError as e:
            await message.answer(e.user_message)
        except Exception:
            await message.answer("Не удалось определить город.")
        return

    if intent.action == IntentAction.ADD_ITEM_HINT:
        await message.answer(
            "Нажмите «➕ Добавить вещь» и отправьте фото с подписью."
        )
        return

    if intent.action == IntentAction.GENERATE_OUTFIT:
        await send_outfit(
            message,
            session,
            destination=intent.destination,
            wishes=intent.wishes or text,
        )
        return

    if intent.action in (IntentAction.ADJUST_OUTFIT, IntentAction.ADVICE):
        await handle_outfit_adjust(message, session, text)
        return

    await message.answer(
        "Попробуйте переформулировать или воспользуйтесь кнопками меню."
    )
