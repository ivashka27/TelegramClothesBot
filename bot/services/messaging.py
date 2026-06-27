from __future__ import annotations

import logging
import re

from aiogram.types import Message, ReplyKeyboardMarkup

logger = logging.getLogger(__name__)

TELEGRAM_MAX_LENGTH = 4096


def _strip_markdown(text: str) -> str:
    return re.sub(r"\*\*([^*]+)\*\*", r"\1", text)


async def safe_answer(
    message: Message,
    text: str,
    *,
    parse_mode: str | None = "Markdown",
    reply_markup: ReplyKeyboardMarkup | None = None,
) -> None:
    chunks = _split_text(text, TELEGRAM_MAX_LENGTH - 50)
    for i, chunk in enumerate(chunks):
        markup = reply_markup if i == len(chunks) - 1 else None
        if parse_mode:
            try:
                await message.answer(chunk, parse_mode=parse_mode, reply_markup=markup)
                continue
            except Exception:
                logger.warning("Markdown send failed, retrying plain text")
        await message.answer(_strip_markdown(chunk), reply_markup=markup)


async def safe_edit_status(
    status_msg: Message,
    message: Message,
    text: str,
    *,
    parse_mode: str | None = "Markdown",
    reply_markup: ReplyKeyboardMarkup | None = None,
) -> None:
    try:
        if parse_mode:
            try:
                await status_msg.edit_text(text, parse_mode=parse_mode)
                return
            except Exception:
                logger.warning("Markdown edit failed, retrying plain text")
        await status_msg.edit_text(_strip_markdown(text))
    except Exception:
        logger.warning("Status edit failed, sending new message")
        await safe_answer(message, text, parse_mode=parse_mode, reply_markup=reply_markup)


def _split_text(text: str, max_len: int) -> list[str]:
    if len(text) <= max_len:
        return [text]
    parts: list[str] = []
    current = ""
    for line in text.split("\n"):
        if len(line) > max_len:
            if current:
                parts.append(current.rstrip())
                current = ""
            for i in range(0, len(line), max_len):
                parts.append(line[i : i + max_len])
            continue
        if len(current) + len(line) + 1 > max_len:
            parts.append(current.rstrip())
            current = line + "\n"
        else:
            current += line + "\n"
    if current.strip():
        parts.append(current.rstrip())
    return parts or [text[:max_len]]
