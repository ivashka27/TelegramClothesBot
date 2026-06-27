# Wardrobe Telegram Bot

Телеграм-бот для подбора образов из личного гардероба с учётом погоды, места назначения и пожеланий пользователя.

## Возможности

- **Гардероб** — загрузка фото вещей с подписью, автоматическое удаление фона
- **Просмотр и удаление** — список вещей или удаление по текстовому запросу (обрабатывает ИИ)
- **Образ на сегодня** — подбор наряда по погоде, месту и пожеланиям
- **Обратная связь** — комментарии к образу: корректировка, совет или подтверждение
- **Свободные запросы** — ИИ определяет намерение и выполняет поддерживаемое действие

## Стек

- Python 3.11+
- [aiogram 3](https://docs.aiogram.dev/) — Telegram Bot API
- SQLAlchemy + SQLite — база данных
- [Alice AI LLM](https://yandex.cloud/ru/docs/ai-studio/) (Yandex Cloud) — подбор образов и NLP
- OpenWeatherMap — погода
- [rembg](https://github.com/danielgatis/rembg) — удаление фона с фото

## Быстрый старт

### 1. Клонирование и окружение

```bash
cd TelegramClothesBot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Ключи API

Скопируйте `.env.example` в `.env` и заполните:

| Переменная | Где получить |
|---|---|
| `BOT_TOKEN` | [@BotFather](https://t.me/BotFather) в Telegram |
| `YANDEX_API_KEY` | [Yandex Cloud Console](https://console.yandex.cloud/) → сервисный аккаунт → API-ключ |
| `YANDEX_FOLDER_ID` | ID каталога в Yandex Cloud (на главной странице консоли) |
| `OPENWEATHER_API_KEY` | [openweathermap.org/api](https://openweathermap.org/api) (бесплатный tier) |

Модель по умолчанию — `aliceai-llm` (Alice AI). Можно заменить на `yandexgpt/latest` или `yandexgpt-lite` через `YANDEX_MODEL`.

### 3. Запуск

```bash
python -m bot.main
```

## Использование

1. `/start` — регистрация и главное меню
2. **Указать город** — нужен для прогноза погоды
3. **Отправить фото** с подписью (`Белая футболка, хлопок`) — вещь попадёт в гардероб
4. **Сгенерировать наряд** — бот учтёт погоду и ваши пожелания
5. **Написать комментарий** — «слишком официально», «замени куртку» и т.д.

### Примеры текстовых запросов

- «Покажи мой гардероб»
- «Удали старые кроссовки»
- «Хочу образ на прогулку, что-то casual»
- «Оставь как есть, но посоветуй аксессуар»

## Структура проекта

```
TelegramClothesBot/
├── bot/
│   ├── main.py              # Точка входа
│   ├── handlers/            # Обработчики Telegram
│   ├── keyboards/           # Клавиатуры
│   ├── services/            # AI, погода, изображения, гардероб
│   └── states/              # FSM-состояния
├── database/
│   ├── models.py            # User, WardrobeItem, OutfitSession
│   └── session.py           # Подключение к БД
├── config.py
├── requirements.txt
└── data/                    # БД и изображения (создаётся автоматически)
```

## Примечания

- Первый запуск `rembg` скачает модель (~170 МБ) — это нормально
- Изображения хранятся локально в `data/wardrobe_images/`
- Для продакшена рекомендуется PostgreSQL вместо SQLite
