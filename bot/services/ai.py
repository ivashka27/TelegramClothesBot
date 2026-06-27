from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum

from openai import APIError, RateLimitError

from bot.services.llm import chat_json
from bot.services.wardrobe import match_items_fuzzy
from database.models import WardrobeItem

logger = logging.getLogger(__name__)


class IntentAction(str, Enum):
    GENERATE_OUTFIT = "generate_outfit"
    LIST_WARDROBE = "list_wardrobe"
    VIEW_ITEM = "view_item"
    DELETE_ITEM = "delete_item"
    CLEAR_WARDROBE = "clear_wardrobe"
    SET_CITY = "set_city"
    SET_PROFILE = "set_profile"
    ADJUST_OUTFIT = "adjust_outfit"
    ADVICE = "advice"
    ADD_ITEM_HINT = "add_item_hint"
    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"


@dataclass
class ParsedIntent:
    action: IntentAction
    message: str
    item_names: list[str]
    destination: str | None = None
    wishes: str | None = None


@dataclass
class OutfitResult:
    item_ids: list[int]
    explanation: str
    advice: str | None = None
    item_tips: str | None = None

_CATEGORY_KEYWORDS = {
    "верх": ["футболк", "рубаш", "свитер", "худи", "блуз", "топ", "поло", "майк"],
    "низ": ["джинс", "брюк", "шорт", "юбк", "леггин"],
    "обувь": ["кроссов", "ботин", "туфл", "сандал", "кед", "сапог", "лофер"],
    "верхняя одежда": ["куртк", "пальто", "пухов", "плащ", "ветров", "парк"],
    "аксессуар": ["сумк", "шапк", "шарф", "часы", "ремен", "очк", "бelt"],
}


def _items_context(items: list[WardrobeItem]) -> str:
    if not items:
        return "Гардероб пуст."
    lines = []
    for item in items:
        cat = f", категория: {item.category}" if item.category else ""
        desc = f", описание: {item.description}" if item.description else ""
        lines.append(f"- id={item.id}, название: «{item.name}»{cat}{desc}")
    return "\n".join(lines)


def _guess_category(text: str) -> str | None:
    lower = text.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return category
    return None


def extract_item_info_local(caption: str) -> tuple[str, str | None, str | None]:
    name = caption.strip() or "Без названия"
    return name, _guess_category(name), None


def parse_user_intent_local(text: str, has_active_outfit: bool) -> ParsedIntent | None:
    lower = text.lower().strip()

    if any(w in lower for w in ("гардероб", "что есть", "что у меня", "мои вещи", "список вещ")):
        return ParsedIntent(IntentAction.LIST_WARDROBE, "", [])

    if any(w in lower for w in ("удали", "убери", "выкини", "delete")):
        return ParsedIntent(IntentAction.DELETE_ITEM, "", [], wishes=text)

    if any(w in lower for w in ("покажи", "показать", "фото", "найди")) and any(
        w in lower for w in ("вещ", "футбол", "джинс", "курт", "обув", "шап", "рубаш")
    ):
        return ParsedIntent(IntentAction.VIEW_ITEM, "", [], wishes=text)

    if any(w in lower for w in ("очисти гардероб", "удали всё", "удали все", "очистить")):
        return ParsedIntent(IntentAction.CLEAR_WARDROBE, "", [])

    if any(w in lower for w in ("рост", "вес", "пол ", "возраст", "телосложение", "размер")):
        return ParsedIntent(IntentAction.SET_PROFILE, "", [], wishes=text)

    if any(w in lower for w in ("наряд", "образ", "одеть", "что надеть", "сгенерируй")):
        return ParsedIntent(IntentAction.GENERATE_OUTFIT, "", [], wishes=text)

    if has_active_outfit and any(
        w in lower for w in ("замени", "поправ", "другой", "официальн", "casual", "слишком")
    ):
        return ParsedIntent(IntentAction.ADJUST_OUTFIT, "", [])

    # Короткий текст без пробелов — скорее всего название города
    if len(text) <= 40 and " " not in text.strip() and not any(c in text for c in "?!."):
        return ParsedIntent(IntentAction.SET_CITY, "", [])

    return None


def match_items_for_deletion_local(
    items: list[WardrobeItem], query: str
) -> list[WardrobeItem]:
    return match_items_fuzzy(items, query)


def _parse_action(raw: dict) -> str:
    action = raw.get("action")
    if isinstance(action, str) and action.strip():
        return action.strip()
    valid = {a.value for a in IntentAction}
    for value in raw.values():
        if isinstance(value, str) and value in valid:
            return value
    return "unknown"


def _coerce_item_ids(raw_ids: list, valid_ids: set[int]) -> list[int]:
    result = []
    for item_id in raw_ids or []:
        try:
            num = int(item_id)
        except (TypeError, ValueError):
            continue
        if num in valid_ids:
            result.append(num)
    return result


def generate_outfit_local(
    items: list[WardrobeItem],
    weather_text: str,
    destination: str | None = None,
    wishes: str | None = None,
) -> OutfitResult:
    """Простой подбор без ИИ: по одной вещи из каждой категории."""
    if not items:
        return OutfitResult(
            item_ids=[],
            explanation="Гардероб пуст. Сначала добавьте вещи — отправьте фото с подписью.",
        )

    temp_match = re.search(r"(-?\d+)(?:°|°C)", weather_text)
    temp = float(temp_match.group(1)) if temp_match else 15.0

    by_category: dict[str, list[WardrobeItem]] = {}
    uncategorized: list[WardrobeItem] = []
    for item in items:
        cat = (item.category or "другое").lower()
        if cat in ("верх", "низ", "обувь", "верхняя одежда", "аксессуар"):
            by_category.setdefault(cat, []).append(item)
        else:
            uncategorized.append(item)

    selected: list[WardrobeItem] = []
    priority = ["верхняя одежда", "верх", "низ", "обувь"] if temp < 12 else ["верх", "низ", "обувь"]
    for cat in priority:
        if cat in by_category and by_category[cat]:
            selected.append(by_category[cat][0])

    if len(selected) < 2:
        for item in uncategorized:
            if item not in selected:
                selected.append(item)
            if len(selected) >= 3:
                break

    if not selected:
        selected = items[: min(3, len(items))]

    dest_part = f" для «{destination}»" if destination else ""
    wish_part = f" Учтены пожелания: {wishes}." if wishes else ""
    explanation = (
        f"Подобрал базовый образ{dest_part} с учётом погоды ({temp:.0f}°C).{wish_part}"
    )
    return OutfitResult(
        item_ids=[i.id for i in selected],
        explanation=explanation,
    )


async def parse_user_intent(text: str, has_active_outfit: bool) -> ParsedIntent:
    local = parse_user_intent_local(text, has_active_outfit)
    if local is not None:
        return local

    try:
        system = """Ты — ассистент телеграм-бота для подбора одежды.
Определи намерение пользователя и верни JSON:
{
  "action": "generate_outfit|list_wardrobe|view_item|delete_item|clear_wardrobe|set_city|set_profile|adjust_outfit|advice|add_item_hint|unknown|unsupported",
  "message": "краткий ответ пользователю если нужен",
  "item_names": ["названия вещей для удаления, если есть"],
  "destination": "куда идёт пользователь, если указано",
  "wishes": "пожелания пользователя, если есть"
}
Отвечай только JSON."""

        raw = await chat_json(
            system,
            f"has_active_outfit={has_active_outfit}\nЗапрос: {text}",
            temperature=0.2,
        )
        intent = ParsedIntent(
            action=IntentAction(_parse_action(raw)),
            message=raw.get("message", ""),
            item_names=raw.get("item_names") or [],
            destination=raw.get("destination"),
            wishes=raw.get("wishes"),
        )
        lower = text.lower()
        if any(w in lower for w in ("удали", "убери", "выкини")) and not any(
            w in lower for w in ("удали всё", "удали все", "очисти")
        ):
            if intent.action != IntentAction.DELETE_ITEM:
                local = parse_user_intent_local(text, has_active_outfit)
                if local and local.action == IntentAction.DELETE_ITEM:
                    return local
        return intent
    except (RateLimitError, APIError) as e:
        logger.warning("Alice AI unavailable for intent parsing: %s", e)
        local = parse_user_intent_local(text, has_active_outfit)
        if local:
            return local
        return ParsedIntent(
            IntentAction.UNKNOWN,
            "Не удалось связаться с Alice AI. Используйте кнопки меню или попробуйте позже.",
            [],
        )
    except (ValueError, KeyError) as e:
        logger.warning("Invalid intent JSON from Alice AI: %s", e)
        local = parse_user_intent_local(text, has_active_outfit)
        if local:
            return local
        return ParsedIntent(IntentAction.UNKNOWN, "", [])


async def generate_outfit(
    items: list[WardrobeItem],
    weather_text: str,
    destination: str | None = None,
    wishes: str | None = None,
) -> OutfitResult:
    if not items:
        return OutfitResult(
            item_ids=[],
            explanation="Гардероб пуст. Сначала добавьте вещи — отправьте фото с подписью.",
        )

    try:
        system = """Ты — стилист. Подбери образ из доступного гардероба пользователя.
Верни JSON:
{
  "item_ids": [...],
  "explanation": "общее описание образа (2-4 предложения)",
  "item_tips": "подробные советы по КАЖДОЙ выбранной вещи: верх, низ, обувь, верхняя одежда — почему подходит, как носить",
  "advice": "дополнительный общий совет или null"
}
Выбирай только существующие id. Обязательно прокомментируй обувь, если она есть в образе."""

        context_parts = [f"Погода:\n{weather_text}", f"Гардероб:\n{_items_context(items)}"]
        if destination:
            context_parts.append(f"Куда идёт: {destination}")
        if wishes:
            context_parts.append(f"Пожелания: {wishes}")

        raw = await chat_json(system, "\n\n".join(context_parts), temperature=0.5)
        valid_ids = {item.id for item in items}
        item_ids = _coerce_item_ids(raw.get("item_ids", []), valid_ids)
        if not item_ids:
            logger.warning("Alice AI returned no valid item_ids: %s", raw)
            return generate_outfit_local(items, weather_text, destination, wishes)
        return OutfitResult(
            item_ids=item_ids,
            explanation=raw.get("explanation", "Образ подобран."),
            advice=raw.get("advice"),
            item_tips=raw.get("item_tips"),
        )
    except (RateLimitError, APIError) as e:
        logger.warning("Alice AI unavailable for outfit generation: %s", e)
        result = generate_outfit_local(items, weather_text, destination, wishes)
        result.explanation += "\n\n⚠️ Alice AI временно недоступна — использован запасной алгоритм."
        return result


async def adjust_outfit(
    items: list[WardrobeItem],
    current_item_ids: list[int],
    weather_text: str,
    feedback: str,
    previous_explanation: str,
) -> OutfitResult:
    try:
        current_items = [i for i in items if i.id in current_item_ids]
        current_desc = _items_context(current_items) if current_items else "нет"

        raw = await chat_json(
            'Стилист. Верни JSON: {"item_ids": [...], "explanation": "...", "advice": null}',
            (
                f"Погода:\n{weather_text}\n\nТекущий образ:\n{current_desc}\n\n"
                f"Комментарий: {feedback}\n\nГардероб:\n{_items_context(items)}"
            ),
            temperature=0.4,
        )
        valid_ids = {item.id for item in items}
        item_ids = _coerce_item_ids(raw.get("item_ids", current_item_ids), valid_ids)
        if not item_ids:
            item_ids = current_item_ids
        return OutfitResult(
            item_ids=item_ids,
            explanation=raw.get("explanation", "Понял ваш комментарий."),
            advice=raw.get("advice"),
        )
    except (RateLimitError, APIError) as e:
        logger.warning("Alice AI unavailable for outfit adjust: %s", e)
        return OutfitResult(
            item_ids=current_item_ids,
            explanation=(
                "Alice AI временно недоступна — образ оставила без изменений."
            ),
        )


async def extract_item_info(caption: str) -> tuple[str, str | None, str | None]:
    try:
        raw = await chat_json(
            (
                'Из подписи к фото одежды извлеки JSON: '
                '{"name": "...", "category": "верх|низ|обувь|...", "description": null}'
            ),
            caption or "без подписи",
            temperature=0.2,
        )
        name = raw.get("name") or caption.strip() or "Без названия"
        return name, raw.get("category"), raw.get("description")
    except (RateLimitError, APIError) as e:
        logger.warning("Alice AI unavailable for item extraction, using local: %s", e)
        return extract_item_info_local(caption)


async def match_items_for_deletion(
    items: list[WardrobeItem], query: str
) -> list[WardrobeItem]:
    if not items:
        return []

    try:
        raw = await chat_json(
            (
                'Пользователь хочет удалить вещи из гардероба. '
                'Верни JSON: {"item_ids": [список id вещей, которые нужно удалить]}. '
                "Если ничего не подходит — верни пустой список."
            ),
            f"Запрос: {query}\n\nГардероб:\n{_items_context(items)}",
            temperature=0.1,
        )
        ids = set(_coerce_item_ids(raw.get("item_ids", []), {item.id for item in items}))
        matched = [item for item in items if item.id in ids]
        if matched:
            return matched
    except (RateLimitError, APIError) as e:
        logger.warning("Alice AI unavailable for deletion matching: %s", e)

    return match_items_for_deletion_local(items, query)


async def match_items_for_viewing(
    items: list[WardrobeItem], query: str
) -> list[WardrobeItem]:
    if not items:
        return []

    try:
        raw = await chat_json(
            'Верни JSON: {"item_ids": [список id вещей, подходящих под запрос]}',
            f"Запрос: {query}\n\nГардероб:\n{_items_context(items)}",
            temperature=0.1,
        )
        ids = set(_coerce_item_ids(raw.get("item_ids", []), {item.id for item in items}))
        return [item for item in items if item.id in ids]
    except (RateLimitError, APIError) as e:
        logger.warning("Alice AI unavailable for view matching: %s", e)
        return match_items_for_deletion_local(items, query)


async def analyze_wardrobe_gaps(
    items: list[WardrobeItem],
    weather_text: str,
    user_profile: str,
) -> str:
    if not items:
        return (
            "Гардероб пуст. Начните с базы: футболка, джинсы/брюки, кроссовки, "
            "лёгкая куртка — и добавьте фото через «➕ Добавить вещь»."
        )

    try:
        raw = await chat_json(
            (
                "Ты — стилист. Проанализируй гардероб и верни JSON: "
                '{"gaps": "список чего не хватает (2-5 пунктов)", '
                '"tips": "краткие советы что докупить в первую очередь"}'
            ),
            (
                f"Погода:\n{weather_text}\n\nПрофиль:\n{user_profile}\n\n"
                f"Гардероб:\n{_items_context(items)}"
            ),
            temperature=0.4,
        )
        gaps = raw.get("gaps") or ""
        tips = raw.get("tips") or ""
        if gaps:
            text = f"🛒 **Чего не хватает:**\n{gaps}"
            if tips:
                text += f"\n\n💡 **Совет:**\n{tips}"
            return text
    except (RateLimitError, APIError) as e:
        logger.warning("Alice AI unavailable for gaps: %s", e)

    categories = {item.category for item in items if item.category}
    missing = []
    for cat in ("верх", "низ", "обувь", "верхняя одежда"):
        if cat not in categories:
            missing.append(cat)
    if missing:
        return (
            "🛒 **Чего не хватает (базовый анализ):**\n"
            + "\n".join(f"• {c}" for c in missing)
            + "\n\n💡 Добавьте недостающие категории через «➕ Добавить вещь»."
        )
    return "✅ Базовый набор категорий есть. Можно уточнить сезонные вещи (шапка, дождевик)."


def _generate_week_outfits_local(
    items: list[WardrobeItem],
    forecasts: list,
    summary: str | None = None,
    *,
    api_down: bool = False,
) -> str:
    lines = ["📅 **План образов на неделю:**\n"]
    for f in forecasts[:5]:
        weather_line = f"{f.day_label}: {f.temperature:.0f}°C, {f.description}"
        result = generate_outfit_local(items, weather_line)
        selected = [i for i in items if i.id in result.item_ids]
        names = ", ".join(i.name for i in selected) if selected else "—"
        lines.append(f"**{f.day_label}** ({names})\n{result.explanation}\n")
    if summary:
        lines.append(f"💡 {summary}")
    if api_down:
        lines.append("\n⚠️ Alice AI временно недоступна — показан упрощённый план.")
    else:
        lines.append("\n💡 План составлен автоматически по погоде и вашему гардеробу.")
    return "\n".join(lines)


async def generate_week_outfits(
    items: list[WardrobeItem],
    forecasts: list,
) -> str:
    if not items:
        return "Сначала добавьте вещи в гардероб."

    forecast_text = "\n".join(f.to_text() for f in forecasts)
    system = (
        "Ты — стилист. Составь план образов на 5 дней из гардероба пользователя.\n"
        "Верни ТОЛЬКО валидный JSON без markdown:\n"
        '{"days":[{"day":"Пн","item_ids":[1,2],"outfit":"краткое описание образа"}],'
        '"summary":"общий совет на неделю"}\n'
        "Правила: item_ids — только существующие id из гардероба. "
        "В days должно быть ровно 5 элементов."
    )

    try:
        raw = await chat_json(
            system,
            f"Прогноз:\n{forecast_text}\n\nГардероб:\n{_items_context(items)}",
            temperature=0.3,
        )
        days = raw.get("days")
        if not isinstance(days, list) or not days:
            logger.warning("Week plan: empty or invalid days in LLM response: %s", raw)
            return _generate_week_outfits_local(
                items, forecasts, raw.get("summary") if isinstance(raw.get("summary"), str) else None
            )

        valid_ids = {item.id for item in items}
        lines = ["📅 **План образов на неделю:**\n"]
        for day in days[:5]:
            day_name = day.get("day", "?") if isinstance(day, dict) else "?"
            desc = (day.get("outfit", "") if isinstance(day, dict) else "") or "—"
            ids = _coerce_item_ids(
                day.get("item_ids", []) if isinstance(day, dict) else [],
                valid_ids,
            )
            names = [i.name for i in items if i.id in ids]
            items_str = ", ".join(names) if names else "—"
            lines.append(f"**{day_name}** ({items_str})\n{desc}\n")
        summary = raw.get("summary")
        if summary:
            lines.append(f"💡 {summary}")
        return "\n".join(lines)
    except (RateLimitError, APIError) as e:
        logger.warning("Alice AI unavailable for week plan: %s", e)
        return _generate_week_outfits_local(items, forecasts, api_down=True)
