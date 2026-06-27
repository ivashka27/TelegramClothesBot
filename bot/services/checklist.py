from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, WardrobeItem


def format_setup_checklist(user: User, items: list[WardrobeItem]) -> str:
    def mark(ok: bool) -> str:
        return "✅" if ok else "⬜"

    has_city = bool(user.city)
    has_profile = any(
        [user.gender, user.height_cm, user.weight_kg, user.clothing_size, user.age]
    )
    has_photo = bool(user.reference_photo_path)
    item_count = len(items)
    has_wardrobe = item_count >= 3

    lines = [
        "📋 **Что настроить перед образами:**\n",
        f"{mark(has_city)} **Город** — для погоды → «📍 Указать город»",
        f"{mark(has_profile)} **Профиль** — рост, размеры → «👤 Мой профиль»",
        f"{mark(has_photo)} **Фото** — для примерки (необязательно) → «📸 Моё фото»",
        f"{mark(has_wardrobe)} **Гардероб** — минимум 3 вещи (сейчас: {item_count}) → «➕ Добавить вещь»",
        "",
    ]

    done = sum([has_city, has_profile, has_photo, has_wardrobe])
    if done == 4:
        lines.append("🎉 Всё готово — жмите «✨ Сгенерировать наряд на сегодня»!")
    elif has_city and has_wardrobe:
        lines.append("👍 Можно генерировать образы. Остальное улучшит точность советов.")
    else:
        missing = []
        if not has_city:
            missing.append("город")
        if not has_wardrobe:
            missing.append("3+ вещи в гардеробе")
        lines.append(f"⚠️ Сначала: {', '.join(missing)}.")

    lines.extend(
        [
            "",
            "💬 **Текстом тоже можно:**",
            "• «удали чёрную футболку» — удалить по описанию",
            "• «покажи джинсы» — показать фото",
            "• «рост 175» — обновить профиль",
        ]
    )
    return "\n".join(lines)
