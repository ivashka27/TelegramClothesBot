from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass

import httpx

from config import settings

logger = logging.getLogger(__name__)

WEATHER_CACHE_TTL_SEC = 20 * 60
_weather_cache: dict[str, tuple[float, "WeatherInfo"]] = {}


@dataclass
class WeatherInfo:
    city: str
    temperature: float
    feels_like: float
    description: str
    humidity: int
    wind_speed: float

    def to_text(self) -> str:
        return (
            f"🌤 {self.city}: {self.temperature:.0f}°C (ощущается как {self.feels_like:.0f}°C)\n"
            f"Условия: {self.description}\n"
            f"Влажность: {self.humidity}%, ветер: {self.wind_speed:.1f} м/с"
        )


class WeatherError(Exception):
    def __init__(self, message: str, user_message: str | None = None):
        super().__init__(message)
        self.user_message = user_message or message


def _city_variants(city: str) -> list[str]:
    city = city.strip()
    variants = [city]
    if "," not in city:
        variants.append(f"{city},ru")
    # OpenWeather иногда лучше находит латиницей
    translit = {
        "москва": "Moscow,ru",
        "санкт-петербург": "Saint Petersburg,ru",
        "петербург": "Saint Petersburg,ru",
        "спб": "Saint Petersburg,ru",
        "новосибирск": "Novosibirsk,ru",
        "екатеринбург": "Yekaterinburg,ru",
        "казань": "Kazan,ru",
    }
    key = city.lower()
    if key in translit:
        variants.append(translit[key])
    return variants


async def _fetch_openweather(city: str) -> WeatherInfo:
    url = "https://api.openweathermap.org/data/2.5/weather"
    last_error: Exception | None = None

    async with httpx.AsyncClient(timeout=15) as client:
        for variant in _city_variants(city):
            params = {
                "q": variant,
                "appid": settings.openweather_api_key,
                "units": "metric",
                "lang": "ru",
            }
            response = await client.get(url, params=params)
            if response.status_code == 401:
                raise WeatherError(
                    "OpenWeather 401",
                    "Ключ OpenWeather не активен или неверный. "
                    "Новые ключи активируются до 2 часов — попробуйте позже.",
                )
            if response.status_code == 404:
                last_error = WeatherError(f"City not found: {variant}")
                continue
            response.raise_for_status()
            data = response.json()
            return WeatherInfo(
                city=data["name"],
                temperature=data["main"]["temp"],
                feels_like=data["main"]["feels_like"],
                description=data["weather"][0]["description"],
                humidity=data["main"]["humidity"],
                wind_speed=data["wind"].get("speed", 0),
            )

    raise last_error or WeatherError(
        f"City not found: {city}",
        f"Не нашёл город «{city}». Попробуйте другое написание.",
    )


async def _fetch_wttr(city: str) -> WeatherInfo:
    """Запасной источник погоды без API-ключа."""
    safe_city = re.sub(r"[^\w\s\-а-яА-ЯёЁ]", "", city.strip()) or city.strip()
    url = f"https://wttr.in/{safe_city}?format=j1&lang=ru"
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(url, headers={"User-Agent": "TelegramClothesBot/1.0"})
        response.raise_for_status()
        data = response.json()

    current = data["current_condition"][0]
    area = data["nearest_area"][0]["areaName"][0]["value"]
    desc = current.get("lang_ru", [{}])[0].get("value") or current["weatherDesc"][0]["value"]

    return WeatherInfo(
        city=area,
        temperature=float(current["temp_C"]),
        feels_like=float(current["FeelsLikeC"]),
        description=desc,
        humidity=int(current["humidity"]),
        wind_speed=float(current["windspeedKmph"]) / 3.6,
    )


async def fetch_weather(city: str, *, use_cache: bool = True) -> WeatherInfo:
    cache_key = city.strip().lower()
    if use_cache and cache_key in _weather_cache:
        ts, cached = _weather_cache[cache_key]
        if time.time() - ts < WEATHER_CACHE_TTL_SEC:
            return cached

    try:
        info = await _fetch_openweather(city)
    except WeatherError as e:
        if "401" in str(e):
            raise
        logger.warning("OpenWeather failed for %r: %s, trying wttr.in", city, e)
        info = None
    except httpx.HTTPError as e:
        logger.warning("OpenWeather HTTP error for %r: %s, trying wttr.in", city, e)
        info = None
    else:
        _weather_cache[cache_key] = (time.time(), info)
        return info

    try:
        info = await _fetch_wttr(city)
        _weather_cache[cache_key] = (time.time(), info)
        return info
    except Exception as e:
        logger.error("wttr.in failed for %r: %s", city, e)
        raise WeatherError(
            str(e),
            f"Не удалось получить погоду для «{city}». Проверьте название города.",
        ) from e


def invalidate_weather_cache(city: str | None = None) -> None:
    if city:
        _weather_cache.pop(city.strip().lower(), None)
    else:
        _weather_cache.clear()


@dataclass
class DayForecast:
    day_label: str
    temperature: float
    description: str

    def to_text(self) -> str:
        return f"{self.day_label}: {self.temperature:.0f}°C, {self.description}"


async def fetch_week_forecast(city: str) -> list[DayForecast]:
    """Прогноз на 5 дней (одна точка в день) через OpenWeather."""
    url = "https://api.openweathermap.org/data/2.5/forecast"
    async with httpx.AsyncClient(timeout=15) as client:
        for variant in _city_variants(city):
            response = await client.get(
                url,
                params={
                    "q": variant,
                    "appid": settings.openweather_api_key,
                    "units": "metric",
                    "lang": "ru",
                },
            )
            if response.status_code == 404:
                continue
            if response.status_code == 401:
                raise WeatherError(
                    "OpenWeather 401",
                    "Ключ OpenWeather не активен. Попробуйте позже.",
                )
            response.raise_for_status()
            data = response.json()
            by_day: dict[str, dict] = {}
            for entry in data.get("list", []):
                dt_txt = entry.get("dt_txt", "")
                day = dt_txt.split(" ")[0] if dt_txt else ""
                if not day or day in by_day:
                    continue
                by_day[day] = entry
                if len(by_day) >= 5:
                    break

            labels = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
            result: list[DayForecast] = []
            for i, (day, entry) in enumerate(sorted(by_day.items())[:5]):
                from datetime import datetime as dt

                try:
                    wd = dt.strptime(day, "%Y-%m-%d").weekday()
                    label = labels[wd]
                except ValueError:
                    label = f"День {i + 1}"
                result.append(
                    DayForecast(
                        day_label=label,
                        temperature=float(entry["main"]["temp"]),
                        description=entry["weather"][0]["description"],
                    )
                )
            if result:
                return result

    current = await fetch_weather(city)
    return [
        DayForecast(
            day_label=f"День {i + 1}",
            temperature=current.temperature + (i - 2),
            description=current.description,
        )
        for i in range(5)
    ]
