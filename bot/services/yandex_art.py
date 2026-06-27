from __future__ import annotations

import asyncio
import base64
import logging
import random
from dataclasses import dataclass

import httpx

from config import settings

logger = logging.getLogger(__name__)

YANDEX_ART_URL = (
    "https://llm.api.cloud.yandex.net/foundationModels/v1/imageGenerationAsync"
)
YANDEX_OPS_URL = "https://llm.api.cloud.yandex.net/operations"


@dataclass
class PreviewResult:
    image: bytes | None
    error: str | None = None  # permission_denied | timeout | api_error


def preview_error_message(error: str | None, has_user_photo: bool) -> str:
    if error == "permission_denied":
        return (
            "🎨 Примерка недоступна: YandexART вернул 403 Permission denied.\n\n"
            "Scope ключа `yc.ai.imageGeneration.execute` — это только половина. "
            "Нужна ещё **роль на каталоге** для сервисного аккаунта, которому принадлежит ключ:\n"
            "• `ai.imageGeneration.user`\n\n"
            "Консоль → каталог → Права доступа → найти сервисный аккаунт → "
            "Добавить роль → AI → `ai.imageGeneration.user`\n\n"
            "Также проверьте, что ключ создан у **того же** сервисного аккаунта "
            "и на каталоге подключён биллинг."
        )
    if error == "timeout":
        return "🎨 Не успела сгенерировать примерку — попробуйте ещё раз чуть позже."
    if not has_user_photo:
        return (
            "🎨 Не удалось сгенерировать примерку. "
            "Загрузите «📸 Моё фото» в профиле — так результат будет точнее."
        )
    return (
        "🎨 Не удалось сгенерировать примерку. "
        "Проверьте настройки YandexART в облаке или попробуйте позже."
    )


async def generate_outfit_preview(
    prompt: str, max_wait_sec: int = 90
) -> PreviewResult:
    """Генерирует минималистичную иллюстрацию образа через YandexART."""
    headers = {
        "Authorization": f"Api-Key {settings.yandex_api_key}",
        "Content-Type": "application/json",
        "x-folder-id": settings.yandex_folder_id,
    }
    body = {
        "modelUri": f"art://{settings.yandex_folder_id}/yandex-art/latest",
        "generationOptions": {
            "seed": random.randint(1, 1_000_000),
            "aspectRatio": {"widthRatio": "2", "heightRatio": "3"},
        },
        "messages": [{"weight": "1", "text": prompt}],
    }

    operation_id: str | None = None

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            create_resp = await client.post(YANDEX_ART_URL, headers=headers, json=body)
            if create_resp.status_code == 403:
                logger.error("YandexART permission denied: %s", create_resp.text)
                return PreviewResult(None, "permission_denied")
            create_resp.raise_for_status()
            operation_id = create_resp.json()["id"]
        except httpx.HTTPStatusError as e:
            logger.error(
                "YandexART create failed (%s): %s",
                e.response.status_code,
                e.response.text,
            )
            return PreviewResult(None, "api_error")
        except Exception:
            logger.exception("YandexART create request failed")
            return PreviewResult(None, "api_error")

        deadline = asyncio.get_event_loop().time() + max_wait_sec
        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(3)
            try:
                status_resp = await client.get(
                    f"{YANDEX_OPS_URL}/{operation_id}", headers=headers
                )
                status_resp.raise_for_status()
                data = status_resp.json()
            except Exception:
                logger.exception("YandexART poll failed")
                continue

            if data.get("done"):
                if data.get("error"):
                    logger.warning("YandexART operation error: %s", data["error"])
                    return PreviewResult(None, "api_error")
                image_b64 = data.get("response", {}).get("image")
                if image_b64:
                    return PreviewResult(base64.b64decode(image_b64))
                logger.warning("YandexART done but no image: %s", data)
                return PreviewResult(None, "api_error")

    logger.warning("YandexART timeout for operation %s", operation_id)
    return PreviewResult(None, "timeout")
