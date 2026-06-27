from __future__ import annotations

import json
import logging
import re

from openai import APIError, AsyncOpenAI, RateLimitError

from config import settings

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key="yandex",
            base_url=settings.yandex_base_url,
            default_headers={
                "Authorization": f"Api-Key {settings.yandex_api_key}",
                "x-folder-id": settings.yandex_folder_id,
            },
        )
    return _client


def model_uri() -> str:
    return f"gpt://{settings.yandex_folder_id}/{settings.yandex_model}/latest"


def _parse_json_content(content: str) -> dict:
    content = (content or "").strip()
    if not content:
        return {}
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
        content = re.sub(r"\s*```$", "", content).strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", content)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    logger.warning("Failed to parse JSON from LLM response: %s", content[:200])
    return {}


async def chat_json(
    system: str,
    user: str,
    temperature: float = 0.3,
) -> dict:
    """Запрос к Alice AI / YandexGPT, ответ парсится как JSON."""
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    kwargs = {
        "model": model_uri(),
        "messages": messages,
        "temperature": temperature,
    }
    client = _get_client()

    try:
        response = await client.chat.completions.create(
            **kwargs,
            response_format={"type": "json_object"},
        )
    except APIError as first_error:
        logger.info("JSON mode failed (%s), retrying without response_format", first_error)
        try:
            response = await client.chat.completions.create(**kwargs)
        except APIError:
            logger.exception("Yandex LLM request failed")
            raise

    content = response.choices[0].message.content or ""
    return _parse_json_content(content)


class LLMUnavailableError(Exception):
    pass
