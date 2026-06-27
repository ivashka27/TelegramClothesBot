from __future__ import annotations

import base64
import logging
from pathlib import Path

from openai import APIError

from bot.services.llm import model_uri, _get_client
from config import settings
from database.models import User

logger = logging.getLogger(__name__)


def user_photo_path(telegram_id: int) -> Path:
    user_dir = settings.storage_path / str(telegram_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir / "reference.jpg"


def save_user_photo(telegram_id: int, image_bytes: bytes) -> str:
    path = user_photo_path(telegram_id)
    path.write_bytes(image_bytes)
    return str(path)


def user_has_saved_photo(user: User) -> bool:
    if not user.reference_photo_path:
        return False
    return Path(user.reference_photo_path).exists()


def delete_user_photo(user: User) -> None:
    if user.reference_photo_path:
        Path(user.reference_photo_path).unlink(missing_ok=True)
    user.reference_photo_path = None
    user.appearance_description = None


async def analyze_user_photo(image_bytes: bytes) -> str:
    """Анализ внешности по фото для генерации примерки."""
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    system = (
        "Ты — стилист. По фото человека составь краткое описание для fashion-иллюстрации. "
        "Укажи: пол (если видно), примерный возраст, телосложение, цвет волос, "
        "рост (если можно оценить), общий стиль. 3–5 предложений на русском. "
        "Без оценочных суждений, только нейтральные факты."
    )

    try:
        client = _get_client()
        response = await client.chat.completions.create(
            model=model_uri(),
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": system},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                        },
                    ],
                }
            ],
            temperature=0.3,
            max_tokens=500,
        )
        text = (response.choices[0].message.content or "").strip()
        if text:
            return text
    except APIError as e:
        logger.warning("Vision analysis unavailable: %s", e)

    return (
        "Человек среднего роста, нейтральное телосложение. "
        "Используйте профиль для уточнения параметров."
    )


def build_person_description(user: User) -> str:
    parts = []
    if user.appearance_description:
        parts.append(user.appearance_description)
    if user.gender:
        parts.append(f"Пол: {user.gender}.")
    if user.age:
        parts.append(f"Возраст: {user.age} лет.")
    if user.height_cm:
        parts.append(f"Рост: {user.height_cm} см.")
    if user.weight_kg:
        parts.append(f"Вес: {user.weight_kg} кг.")
    if user.body_type:
        parts.append(f"Телосложение: {user.body_type}.")
    if user.clothing_size:
        parts.append(f"Размер одежды: {user.clothing_size}.")
    return " ".join(parts) if parts else "Человек среднего роста, casual стиль."


def build_outfit_preview_prompt_local(user: User, outfit_items_description: str) -> str:
    person = build_person_description(user)
    return (
        "Minimalist flat fashion illustration, full body, white background, clean lines, "
        f"no text, no face details. Person: {person}. Outfit: {outfit_items_description}."
    )


async def build_outfit_preview_prompt(
    user: User, outfit_items_description: str
) -> str:
    return build_outfit_preview_prompt_local(user, outfit_items_description)
