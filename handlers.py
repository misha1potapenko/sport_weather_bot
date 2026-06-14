from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from logger import log_user_request
from keyboards import get_main_reply_keyboard
from weather_api import get_weather_forecast

router = Router()

class WeatherState(StatesGroup):
    waiting_city = State()

async def safe_send(message: Message, text: str):
    if len(text) > 4096:
        for x in range(0, len(text), 4096):
            await message.answer(text[x:x+4096])
    else:
        await message.answer(text)

def format_hourly_forecast(data: dict, day_label: str) -> str:
    city = data["city_info"]["name"]
    hourly = data["hourly"]
    times = hourly["time"]
    result = f"🌍 🌡️ Прогноз погоды для {city} ({day_label})\nМодель ECMWF IFS HRES (9 км)\nИнтервалы по 3 часа\n\n"
    for start_hour in range(0, 24, 3):
        end_hour = start_hour + 3
        temps, winds, probs, total_precip, count = [], [], [], 0.0, 0
        for i, time in enumerate(times):
            dt = datetime.fromisoformat(time)
            hour = dt.hour
            if start_hour <= hour < end_hour:
                temps.append(hourly["temperature_2m"][i])
                winds.append(hourly["wind_speed_10m"][i])
                probs.append(hourly["precipitation_probability"][i])
                rain = hourly.get("rain", [0])[i] if i < len(hourly.get("rain", [])) else 0
                showers = hourly.get("showers", [0])[i] if i < len(hourly.get("showers", [])) else 0
                total_precip += rain + showers
                count += 1
        if count == 0:
            continue
        avg_temp = sum(temps) / count
        avg_wind = sum(winds) / count
        max_prob = max(probs)
        rain_emoji = "☔ " if total_precip > 0.1 else ""
        result += f"{start_hour:02d}:00-{end_hour:02d}:00  🌡️{avg_temp:.1f}°C  💨{avg_wind:.1f} км/ч\n"
        result += f"{rain_emoji}Осадки: {total_precip:.1f} мм (вероятность {max_prob:.0f}%)\n------------------------\n"
    return result


def format_weekly_forecast(data: dict) -> str:
    city = data["city_info"]["name"]
    daily = data["daily"]
    hourly = data.get("hourly", {})
    daily_times = daily["time"]

    hourly_times = hourly.get("time", [])
    hourly_rain = hourly.get("rain", [])
    hourly_showers = hourly.get("showers", [])
    hourly_prob = hourly.get("precipitation_probability", [])

    result = f"🌍 🌡️ Прогноз погоды для {city} на неделю\nМодель ECMWF IFS HRES\n\n"

    for i, day_time in enumerate(daily_times):
        day_date = datetime.fromisoformat(day_time)
        day_name = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][day_date.weekday()]

        temp_max = daily["temperature_2m_max"][i]
        temp_min = daily["temperature_2m_min"][i]
        wind_max = daily["wind_speed_10m_max"][i]

        # Собираем часы с осадками для этого дня (индекс и время)
        rain_hours = []
        for j, hour_time in enumerate(hourly_times):
            if hour_time.startswith(day_time.split("T")[0]):
                rain_val = hourly_rain[j] if j < len(hourly_rain) else 0
                showers_val = hourly_showers[j] if j < len(hourly_showers) else 0
                prob_val = hourly_prob[j] if j < len(hourly_prob) else 0
                total_precip_hour = rain_val + showers_val
                if total_precip_hour > 0.1 or prob_val > 30:
                    hour_str = hour_time.split("T")[1][:5]
                    rain_hours.append((j, hour_str))

        # Группируем последовательные часы в интервалы
        intervals = []
        if rain_hours:
            current = [rain_hours[0][1]]
            for k in range(1, len(rain_hours)):
                if rain_hours[k][0] == rain_hours[k - 1][0] + 1:
                    current.append(rain_hours[k][1])
                else:
                    intervals.append(current)
                    current = [rain_hours[k][1]]
            intervals.append(current)

        # Формируем описание осадков
        if not intervals:
            rain_desc = "🌤️ Осадков не ожидается"
            rain_emoji = ""
        else:
            parts = []
            for interval in intervals:
                start = interval[0]
                end = interval[-1]
                if start == end:
                    parts.append(start)
                else:
                    parts.append(f"{start}-{end}")
            rain_desc = "☔ Дождь: " + ", ".join(parts)
            rain_emoji = "☔ "

        result += f"{day_name} {day_time}\n🌡️ макс: {temp_max:.1f}°C, мин: {temp_min:.1f}°C\n💨 ветер макс: {wind_max:.1f} км/ч\n"
        result += f"{rain_desc}\n--------------------\n"

    return result

@router.message(CommandStart())
async def start_command(message: Message):
    await message.answer(
        "Привет! Я бот прогноза погоды.\nИспользую модель ECMWF IFS HRES.\n\nНажми на одну из кнопок внизу, затем напиши название города.",
        reply_markup=get_main_reply_keyboard()
    )

@router.message(F.text.in_(["🌤 Прогноз на сегодня", "⛅ Прогноз на завтра", "📅 Прогноз на неделю"]))
async def reply_button_handler(message: Message, state: FSMContext):
    text = message.text
    if text == "🌤 Прогноз на сегодня":
        await state.update_data(forecast_type="today", day_label="сегодня")
    elif text == "⛅ Прогноз на завтра":
        await state.update_data(forecast_type="tomorrow", day_label="завтра")
    else:
        await state.update_data(forecast_type="weekly", day_label=None)
    await state.set_state(WeatherState.waiting_city)
    await message.answer("Введите название города:")

@router.message(WeatherState.waiting_city, F.text)
async def process_city_input(message: Message, state: FSMContext):
    city = message.text.strip()
    if len(city) < 2:
        await message.answer("Слишком короткое название. Введите полное название города.")
        return
    data = await state.get_data()
    forecast_type = data.get("forecast_type")
    day_label = data.get("day_label")
    processing = await message.answer("⏳ Получаю данные с Open-Meteo...")
    forecast_data = await get_weather_forecast(city, forecast_type)
    await processing.delete()
    if "error" in forecast_data:
        await message.answer(f"Ошибка: {forecast_data['error']}\nПопробуйте другой город или /start.")
        await state.clear()
        return
    if forecast_type == "weekly":
        response = format_weekly_forecast(forecast_data)
    else:
        response = format_hourly_forecast(forecast_data, day_label)
    username = message.from_user.username
    log_user_request(city, message.from_user.id, username)
    await safe_send(message, response)
    await state.clear()
    await message.answer("Выберите другую кнопку внизу.", reply_markup=get_main_reply_keyboard())

@router.message(F.text, ~StateFilter(WeatherState.waiting_city))
async def text_city_fallback(message: Message):
    city = message.text.strip()
    if len(city) < 2:
        return
    processing = await message.answer("⏳ Получаю прогноз на неделю (по умолчанию)...")
    forecast_data = await get_weather_forecast(city, "weekly")
    await processing.delete()
    if "error" in forecast_data:
        await message.answer(f"Город '{city}' не найден. Нажмите кнопку и введите город ещё раз.")
        return
    response = format_weekly_forecast(forecast_data)
    username = message.from_user.username
    log_user_request(city, message.from_user.id, username)
    await safe_send(message, response)