from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.formatting import format_wardrobe_list_markdown
from database.models import OutfitSession, User, WardrobeItem


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
) -> User:
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    if user:
        if username and user.username != username:
            user.username = username
        if first_name and user.first_name != first_name:
            user.first_name = first_name
        await session.commit()
        return user

    user = User(telegram_id=telegram_id, username=username, first_name=first_name)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def set_user_city(session: AsyncSession, user: User, city: str) -> None:
    user.city = city.strip()
    await session.commit()


async def get_wardrobe_items(session: AsyncSession, user_id: int) -> list[WardrobeItem]:
    result = await session.execute(
        select(WardrobeItem)
        .where(WardrobeItem.user_id == user_id)
        .order_by(WardrobeItem.created_at.desc())
    )
    return list(result.scalars().all())


async def add_wardrobe_item(
    session: AsyncSession,
    user_id: int,
    name: str,
    original_path: str,
    processed_path: str,
    category: str | None = None,
    description: str | None = None,
) -> WardrobeItem:
    item = WardrobeItem(
        user_id=user_id,
        name=name,
        category=category,
        description=description,
        original_image_path=original_path,
        processed_image_path=processed_path,
    )
    session.add(item)
    await session.flush()
    await session.commit()
    await session.refresh(item)
    return item


async def delete_wardrobe_items(
    session: AsyncSession, items: list[WardrobeItem]
) -> list[str]:
    deleted_names = []
    for item in items:
        deleted_names.append(item.name)
        for path in (item.original_image_path, item.processed_image_path):
            p = Path(path)
            if p.exists():
                p.unlink()
        await session.delete(item)
    await session.commit()
    return deleted_names


async def get_latest_outfit_session(
    session: AsyncSession, user_id: int
) -> OutfitSession | None:
    result = await session.execute(
        select(OutfitSession)
        .where(OutfitSession.user_id == user_id)
        .order_by(OutfitSession.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def create_outfit_session(
    session: AsyncSession,
    user_id: int,
    weather_data: str,
    item_ids: list[int],
    ai_response: str,
    destination: str | None = None,
    wishes: str | None = None,
) -> OutfitSession:
    outfit = OutfitSession(
        user_id=user_id,
        weather_data=weather_data,
        selected_item_ids=",".join(str(i) for i in item_ids),
        ai_response=ai_response,
        destination=destination,
        user_wishes=wishes,
    )
    session.add(outfit)
    await session.commit()
    await session.refresh(outfit)
    return outfit


async def update_outfit_session(
    session: AsyncSession,
    outfit: OutfitSession,
    item_ids: list[int],
    ai_response: str,
    feedback: str,
) -> OutfitSession:
    outfit.selected_item_ids = ",".join(str(i) for i in item_ids)
    outfit.ai_response = ai_response
    outfit.user_feedback = feedback
    await session.commit()
    await session.refresh(outfit)
    return outfit


def parse_item_ids(raw: str | None) -> list[int]:
    if not raw:
        return []
    ids = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            ids.append(int(part))
    return ids


def format_wardrobe_list(items: list[WardrobeItem]) -> str:
    if not items:
        return (
            "👗 Ваш гардероб пока пуст.\n\n"
            "Нажмите «➕ Добавить вещь» и отправьте фото с подписью."
        )
    return format_wardrobe_list_markdown(items)


async def clear_wardrobe(session: AsyncSession, user_id: int) -> int:
    items = await get_wardrobe_items(session, user_id)
    if not items:
        return 0
    await delete_wardrobe_items(session, items)
    return len(items)


def normalize_item_search_query(query: str) -> str:
    q = query.lower().replace("ё", "е").strip()
    for prefix in (
        "удали ",
        "убери ",
        "выкини ",
        "delete ",
        "удалить ",
        "покажи ",
        "показать ",
        "найди ",
    ):
        if q.startswith(prefix):
            q = q[len(prefix) :].strip()
    for art in ("мою ", "моё ", "мой ", "моя ", "the "):
        if q.startswith(art):
            q = q[len(art) :].strip()
    return q.strip(" .,!?:\"'-")


def _word_matches(query_word: str, name: str) -> bool:
    if len(query_word) < 3:
        return False
    qw = query_word.replace("ё", "е")
    name_norm = name.lower().replace("ё", "е")
    if qw in name_norm:
        return True
    for nw in name_norm.split():
        if qw in nw or nw in qw:
            return True
        stem = min(4, len(qw), len(nw))
        if stem >= 3 and qw[:stem] == nw[:stem]:
            return True
    return False


def match_items_fuzzy(items: list[WardrobeItem], query: str) -> list[WardrobeItem]:
    q = normalize_item_search_query(query)
    if not q or not items:
        return []

    matched: list[WardrobeItem] = []
    seen: set[int] = set()

    for item in items:
        name = item.name.lower().replace("ё", "е")
        if q in name or name in q:
            if item.id not in seen:
                matched.append(item)
                seen.add(item.id)

    if matched:
        return matched

    words = [w for w in q.split() if len(w) >= 3]
    if not words:
        return []

    for item in items:
        name = item.name.lower().replace("ё", "е")
        if all(_word_matches(w, name) for w in words):
            if item.id not in seen:
                matched.append(item)
                seen.add(item.id)
    return matched


def match_items_by_names(items: list[WardrobeItem], text: str) -> list[WardrobeItem]:
    if not items or not text.strip():
        return []

    parts = [p.strip() for p in re.split(r"[,;\n]+", text) if p.strip()]
    if len(parts) == 1:
        fuzzy = match_items_fuzzy(items, parts[0])
        if fuzzy:
            return fuzzy

    matched: list[WardrobeItem] = []
    seen_ids: set[int] = set()

    for part in parts:
        part_lower = part.lower().replace("ё", "е")
        found = False
        for item in items:
            if item.id in seen_ids:
                continue
            name_lower = item.name.lower().replace("ё", "е")
            if part_lower == name_lower or part_lower in name_lower or name_lower in part_lower:
                matched.append(item)
                seen_ids.add(item.id)
                found = True
                break
        if not found:
            for item in match_items_fuzzy(items, part):
                if item.id not in seen_ids:
                    matched.append(item)
                    seen_ids.add(item.id)
    return matched
