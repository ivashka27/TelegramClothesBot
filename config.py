from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    bot_token: str

    # Yandex Cloud — Alice AI LLM (OpenAI-совместимый API)
    yandex_api_key: str
    yandex_folder_id: str
    yandex_model: str = "aliceai-llm"
    yandex_base_url: str = "https://llm.api.cloud.yandex.net/v1"

    openweather_api_key: str
    database_url: str = "sqlite+aiosqlite:///./data/wardrobe.db"
    storage_path: Path = Path("./data/wardrobe_images")

    def ensure_dirs(self) -> None:
        self.storage_path.mkdir(parents=True, exist_ok=True)
        Path("./data").mkdir(parents=True, exist_ok=True)


settings = Settings()
