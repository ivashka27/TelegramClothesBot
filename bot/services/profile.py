from __future__ import annotations

import re
from typing import Optional

from database.models import User

PROFILE_FIELDS = {
    "пол": "gender",
    "gender": "gender",
    "рост": "height_cm",
    "height": "height_cm",
    "вес": "weight_kg",
    "weight": "weight_kg",
    "размер обуви": "shoe_size",
    "обувь": "shoe_size",
    "shoe": "shoe_size",
    "размер одежды": "clothing_size",
    "размер": "clothing_size",
    "clothing": "clothing_size",
    "возраст": "age",
    "age": "age",
    "телосложение": "body_type",
    "body": "body_type",
}


def format_user_profile(user: User) -> str:
    def val(v) -> str:
        return str(v) if v is not None else "не указано"

    photo = "✅ загружено" if user.reference_photo_path else "не загружено"
    appearance = (
        (user.appearance_description[:120] + "…")
        if user.appearance_description and len(user.appearance_description) > 120
        else (user.appearance_description or "не проанализировано")
    )
    return (
        "👤 **Ваш профиль:**\n\n"
        f"• Пол: {val(user.gender)}\n"
        f"• Рост: {val(user.height_cm)}{' см' if user.height_cm else ''}\n"
        f"• Вес: {val(user.weight_kg)}{' кг' if user.weight_kg else ''}\n"
        f"• Размер обуви: {val(user.shoe_size)}\n"
        f"• Размер одежды: {val(user.clothing_size)}\n"
        f"• Возраст: {val(user.age)}\n"
        f"• Телосложение: {val(user.body_type)}\n"
        f"• Фото для примерки: {photo}\n"
        f"• AI-описание: {appearance}\n\n"
        "Чтобы изменить параметр, нажмите «✏️ Изменить параметры» или напишите, "
        "например: «рост 175» или «пол женский»."
    )


def parse_profile_update(text: str) -> list[tuple[str, str]]:
    """Парсит «рост 175, вес 70» или «пол: мужской»."""
    updates: list[tuple[str, str]] = []
    text = text.strip().lower()
    if not text:
        return updates

    for key, field in sorted(PROFILE_FIELDS.items(), key=lambda x: -len(x[0])):
        patterns = [
            rf"{re.escape(key)}\s*[:=]?\s*([^,;\n]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                value = match.group(1).strip()
                if value and (field, value) not in [(u[0], u[1]) for u in updates]:
                    updates.append((field, value))
                text = text.replace(match.group(0), " ")

    return updates


def apply_profile_field(user: User, field: str, raw_value: str) -> Optional[str]:
    value = raw_value.strip()
    if field == "height_cm":
        num = re.search(r"\d+", value)
        if not num:
            return "Укажите рост числом, например: 175"
        user.height_cm = int(num.group())
    elif field == "weight_kg":
        num = re.search(r"[\d.]+", value.replace(",", "."))
        if not num:
            return "Укажите вес числом, например: 70"
        user.weight_kg = float(num.group())
    elif field == "age":
        num = re.search(r"\d+", value)
        if not num:
            return "Укажите возраст числом"
        user.age = int(num.group())
    elif field == "gender":
        user.gender = value
    elif field == "shoe_size":
        user.shoe_size = value
    elif field == "clothing_size":
        user.clothing_size = value
    elif field == "body_type":
        user.body_type = value
    else:
        return f"Неизвестное поле: {field}"
    return None
