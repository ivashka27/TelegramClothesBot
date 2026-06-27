from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.wardrobe import parse_item_ids
from database.models import FavoriteOutfit, OutfitSession, User

EMPTY_FAVORITES_TEXT = (
    "⭐ Избранных образов пока нет.\n\n"
    "Сгенерируйте наряд и нажмите «⭐ В избранное» под сообщением."
)


async def save_favorite_from_session(
    session: AsyncSession, user: User, outfit: OutfitSession, title: str | None = None
) -> FavoriteOutfit:
    fav = FavoriteOutfit(
        user_id=user.id,
        title=title or f"Образ от {outfit.created_at.strftime('%d.%m')}",
        item_ids=outfit.selected_item_ids or "",
        explanation=outfit.ai_response,
    )
    session.add(fav)
    await session.commit()
    await session.refresh(fav)
    return fav


async def get_favorites(session: AsyncSession, user_id: int) -> list[FavoriteOutfit]:
    result = await session.execute(
        select(FavoriteOutfit)
        .where(FavoriteOutfit.user_id == user_id)
        .order_by(FavoriteOutfit.created_at.desc())
    )
    return list(result.scalars().all())


def format_favorites_list(
    favs: list[FavoriteOutfit], items_by_id: dict[int, str]
) -> str:
    lines = ["⭐ **Избранные образы:**\n"]
    for fav in favs[:10]:
        ids = parse_item_ids(fav.item_ids)
        names = [items_by_id.get(i, f"id={i}") for i in ids]
        lines.append(f"**{fav.title}**")
        lines.append("• " + ", ".join(names) if names else "• (вещи удалены)")
        if fav.explanation:
            short = fav.explanation[:120] + ("…" if len(fav.explanation) > 120 else "")
            lines.append(f"_{short}_")
        lines.append("")
    lines.append("_Нажмите 🗑 под образом, чтобы удалить._")
    return "\n".join(lines)


async def delete_favorite(
    session: AsyncSession, user_id: int, favorite_id: int
) -> bool:
    result = await session.execute(
        select(FavoriteOutfit).where(
            FavoriteOutfit.id == favorite_id,
            FavoriteOutfit.user_id == user_id,
        )
    )
    fav = result.scalar_one_or_none()
    if not fav:
        return False
    await session.delete(fav)
    await session.commit()
    return True
