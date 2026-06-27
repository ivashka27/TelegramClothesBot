import io
import logging
from pathlib import Path

from PIL import Image
from rembg import remove, new_session

from config import settings

logger = logging.getLogger(__name__)

_session = None


def init_rembg_session() -> None:
    """Предзагрузка модели rembg при старте бота (в фоне)."""
    global _session
    if _session is None:
        logger.info("Loading rembg model...")
        _session = new_session("u2net")
        logger.info("rembg model ready")


def remove_background(image_bytes: bytes) -> bytes:
    """Удаляет фон с фото вещи. Вызывать через run_in_executor."""
    global _session
    if _session is None:
        _session = new_session("u2net")
    input_image = Image.open(io.BytesIO(image_bytes))
    output_image = remove(input_image, session=_session)
    buffer = io.BytesIO()
    output_image.save(buffer, format="PNG")
    return buffer.getvalue()


def save_wardrobe_images(
    user_telegram_id: int,
    item_id: int,
    original_bytes: bytes,
    processed_bytes: bytes,
) -> tuple[str, str]:
    user_dir = settings.storage_path / str(user_telegram_id)
    user_dir.mkdir(parents=True, exist_ok=True)

    original_path = user_dir / f"{item_id}_original.jpg"
    processed_path = user_dir / f"{item_id}_processed.png"

    original_path.write_bytes(original_bytes)
    processed_path.write_bytes(processed_bytes)

    return str(original_path), str(processed_path)
