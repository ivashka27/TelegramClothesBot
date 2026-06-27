import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.fsm import cancel_keyboard
from bot.keyboards.menus import (
    BTN_GAPS,
    BTN_GENERATE,
    BTN_SET_CITY,
    BTN_TWO_VARIANTS,
    BTN_WEEK_PLAN,
    main_menu,
)
from bot.services.ai import analyze_wardrobe_gaps, generate_week_outfits
from bot.services.messaging import safe_answer, safe_edit_status
from bot.services.outfit_service import send_outfit, send_two_outfits
from bot.services.profile import format_user_profile
from bot.services.wardrobe import get_or_create_user, get_wardrobe_items, set_user_city
from bot.services.weather import WeatherError, fetch_weather, fetch_week_forecast, invalidate_weather_cache
from bot.states.conversation import UserStates

logger = logging.getLogger(__name__)

router = Router()


@router.message(F.text == BTN_GENERATE)
async def btn_generate_outfit(
    message: Message, session: AsyncSession, state: FSMContext
) -> None:
    user = await get_or_create_user(session, telegram_id=message.from_user.id)
    if not user.city:
        await message.answer(
            "📍 Сначала укажите город.\n"
            "Или откройте «📋 Что настроить» — там чеклист."
        )
        return
    await state.set_state(UserStates.waiting_outfit_details)
    await message.answer(
        "Куда планируете идти и есть ли пожелания?\n\n"
        "Например: «На работу, хочу что-то строгое»\n"
        "Или «-» — подберу только по погоде.\n\n"
        "◀️ Назад или 🏠 В меню — выйти.",
        reply_markup=cancel_keyboard(),
    )


@router.message(F.text == BTN_TWO_VARIANTS)
async def btn_two_variants(
    message: Message, session: AsyncSession, state: FSMContext
) -> None:
    user = await get_or_create_user(session, telegram_id=message.from_user.id)
    if not user.city:
        await message.answer("📍 Сначала укажите город.")
        return
    await state.set_state(UserStates.waiting_outfit_details)
    await state.update_data(two_variants=True)
    await message.answer(
        "👔 Подберу **два варианта**: casual и более строгий.\n\n"
        "Куда идёте? Напишите пожелания или «-».\n"
        "◀️ Назад или 🏠 В меню — выйти.",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard(),
    )


@router.message(UserStates.waiting_outfit_details)
async def outfit_details_received(
    message: Message, session: AsyncSession, state: FSMContext
) -> None:
    data = await state.get_data()
    two_variants = data.get("two_variants", False)
    await state.clear()

    text = (message.text or "").strip()
    destination = None
    wishes = None

    if text and text.lower() not in ("-", "нет", "no", "ничего"):
        if "," in text:
            parts = text.split(",", 1)
            destination = parts[0].strip()
            wishes = parts[1].strip() if len(parts) > 1 else None
        else:
            wishes = text

    if two_variants:
        await send_two_outfits(message, session, destination=destination, base_wishes=wishes)
    else:
        await send_outfit(message, session, destination=destination, wishes=wishes)


@router.message(F.text == BTN_WEEK_PLAN)
async def btn_week_plan(message: Message, session: AsyncSession) -> None:
    user = await get_or_create_user(session, telegram_id=message.from_user.id)
    if not user.city:
        await message.answer("📍 Сначала укажите город.")
        return
    items = await get_wardrobe_items(session, user.id)
    if not items:
        await message.answer("Сначала добавьте вещи в гардероб.")
        return

    status = await message.answer("⏳ Составляю план на неделю...")
    try:
        forecasts = await fetch_week_forecast(user.city)
        plan = await generate_week_outfits(items, forecasts)
        try:
            await status.delete()
        except Exception:
            pass
        await safe_answer(message, plan, reply_markup=main_menu())
    except WeatherError as e:
        await safe_edit_status(status, message, e.user_message, parse_mode=None, reply_markup=main_menu())
    except Exception:
        logger.exception("Week plan failed")
        await safe_edit_status(
            status,
            message,
            "❌ Не удалось составить план. Попробуйте позже.",
            parse_mode=None,
            reply_markup=main_menu(),
        )


@router.message(F.text == BTN_GAPS)
async def btn_gaps(message: Message, session: AsyncSession) -> None:
    user = await get_or_create_user(session, telegram_id=message.from_user.id)
    items = await get_wardrobe_items(session, user.id)
    status = await message.answer("⏳ Анализирую гардероб...")
    try:
        weather_text = "город не указан"
        if user.city:
            weather = await fetch_weather(user.city)
            weather_text = weather.to_text()
        profile = format_user_profile(user)
        text = await analyze_wardrobe_gaps(items, weather_text, profile)
        try:
            await status.delete()
        except Exception:
            pass
        await safe_answer(message, text, reply_markup=main_menu())
    except Exception:
        logger.exception("Wardrobe gaps analysis failed")
        await safe_edit_status(
            status,
            message,
            "❌ Не удалось проанализировать гардероб.",
            parse_mode=None,
            reply_markup=main_menu(),
        )


@router.message(F.text == BTN_SET_CITY)
async def btn_set_city(message: Message, state: FSMContext) -> None:
    await state.set_state(UserStates.waiting_city)
    await message.answer(
        "Напишите название города, например: Москва\n\n"
        "◀️ Назад или 🏠 В меню — выйти.",
        reply_markup=cancel_keyboard(),
    )


@router.message(UserStates.waiting_city)
async def city_received(
    message: Message, session: AsyncSession, state: FSMContext
) -> None:
    await state.clear()
    city = (message.text or "").strip()
    if not city:
        await message.answer("Город не может быть пустым. Попробуйте ещё раз.")
        return

    user = await get_or_create_user(session, telegram_id=message.from_user.id)
    try:
        weather = await fetch_weather(city, use_cache=False)
        await set_user_city(session, user, weather.city)
        invalidate_weather_cache()
        await message.answer(
            f"✅ Город сохранён: **{weather.city}**\n\n{weather.to_text()}",
            parse_mode="Markdown",
            reply_markup=main_menu(),
        )
    except WeatherError as e:
        await message.answer(e.user_message, reply_markup=main_menu())
    except Exception:
        await message.answer(
            "Не удалось сохранить город. Проверьте название и попробуйте снова.",
            reply_markup=main_menu(),
        )
