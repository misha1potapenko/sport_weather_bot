import aiohttp
from datetime import datetime, timedelta
from typing import Dict, Any

from config import OPEN_METEO_BASE_URL, HOURLY_VARIABLES, DAILY_VARIABLES

async def get_coordinates(city_name: str) -> Dict[str, float]:
    geocoding_url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": city_name, "count": 1, "language": "ru", "format": "json"}
    async with aiohttp.ClientSession() as session:
        async with session.get(geocoding_url, params=params) as response:
            data = await response.json()
            if data.get("results"):
                location = data["results"][0]
                return {"lat": location["latitude"], "lon": location["longitude"], "name": location["name"]}
    return None

async def get_weather_forecast(city_name: str, forecast_type: str) -> Dict[str, Any]:
    coords = await get_coordinates(city_name)
    if not coords:
        return {"error": "Город не найден"}

    now = datetime.now()
    if forecast_type == "today":
        start_date = now.strftime("%Y-%m-%d")
        end_date = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        params = {
            "latitude": coords["lat"],
            "longitude": coords["lon"],
            "timezone": "auto",
            "models": "ecmwf_ifs",
            "hourly": ",".join(HOURLY_VARIABLES),
            "start_date": start_date,
            "end_date": end_date
        }
    elif forecast_type == "tomorrow":
        tomorrow = now + timedelta(days=1)
        start_date = tomorrow.strftime("%Y-%m-%d")
        end_date = (tomorrow + timedelta(days=1)).strftime("%Y-%m-%d")
        params = {
            "latitude": coords["lat"],
            "longitude": coords["lon"],
            "timezone": "auto",
            "models": "ecmwf_ifs",
            "hourly": ",".join(HOURLY_VARIABLES),
            "start_date": start_date,
            "end_date": end_date
        }
    else:  # weekly (7 дней)
        end_date = (now + timedelta(days=6)).strftime("%Y-%m-%d")
        params = {
            "latitude": coords["lat"],
            "longitude": coords["lon"],
            "timezone": "auto",
            "models": "ecmwf_ifs",
            "daily": ",".join(DAILY_VARIABLES),
            "hourly": ",".join(HOURLY_VARIABLES),   # добавляем почасовые данные для анализа осадков
            "start_date": now.strftime("%Y-%m-%d"),
            "end_date": end_date
        }

    async with aiohttp.ClientSession() as session:
        async with session.get(OPEN_METEO_BASE_URL, params=params) as response:
            if response.status == 200:
                data = await response.json()
                data["city_info"] = coords
                return data
            else:
                return {"error": f"Ошибка API: {response.status}"}