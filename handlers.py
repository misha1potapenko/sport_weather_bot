from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta

from keyboards import get_main_keyboard
from weather_api import get_weather_forecast

router = Router()


class WeatherStates(StatesGroup):
    waiting_for_city = State()  # Состояние ожидания ввода города


@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    await state.clear()  # Сброс состояния, если бот был перезапущен
    await message.answer(
        "Привет! Я бот прогноза погоды 🌤\n\n"
        "Я использую самую точную модель ECMWF IFS HRES от Open-Meteo.\n\n"
        "Чтобы начать, просто нажмите на одну из кнопок ниже и введите название города.",
        reply_markup=get_main_keyboard()
    )


@router.callback_query(F.data.in_(["forecast_3days", "forecast_today", "forecast_tomorrow"]))
async def ask_city(callback: CallbackQuery, state: FSMContext):
    """Запрашивает у пользователя название города"""
    await state.update_data(forecast_type=callback.data)
    await callback.message.answer("Введите название города:")
    await state.set_state(WeatherStates.waiting_for_city)
    await callback.answer()


@router.message(WeatherStates.waiting_for_city)
async def process_city(message: Message, state: FSMContext):
    """Обрабатывает введённый город и отправляет прогноз"""
    city_name = message.text.strip()
    user_data = await state.get_data()
    forecast_type = user_data.get("forecast_type")

    if not forecast_type:
        await message.answer("Пожалуйста, начните заново через /start")
        await state.clear()
        return
    await message.answer("⏳ Получаю данные...", request_timeout=60)
    # Показываем, что бот обрабатывает запрос
    processing_msg = await message.answer("⏳ Получаю данные с Open-Meteo ECMWF IFS HRES...")

    # Получаем прогноз
    forecast_data = await get_weather_forecast(city_name, forecast_type.replace("forecast_", ""))

    await processing_msg.delete()  # Удаляем сообщение "Получаю данные"

    if "error" in forecast_data:
        await message.answer(f"❌ Ошибка: {forecast_data['error']}\nПопробуйте другой город.")
        await state.clear()
        return

    # Форматируем и отправляем прогноз
    if forecast_type == "forecast_3days":
        response_text = format_daily_forecast(forecast_data)
    else:  # today или tomorrow
        response_text = format_hourly_forecast(forecast_data, forecast_type)

    # Разбиваем длинные сообщения на части
    if len(response_text) > 4096:
        for x in range(0, len(response_text), 4096):
            await message.answer(response_text[x:x + 4096])
    else:
        await message.answer(response_text)

    await state.clear()
    await message.answer("Что ещё вас интересует?", reply_markup=get_main_keyboard())


def format_daily_forecast(data: dict) -> str:
    """Форматирует прогноз на 3 дня (основная температура, ветер, осадки)"""
    city = data["city_info"]["name"]
    daily = data["daily"]
    hourly = data.get("hourly", {})
    daily_times = daily["time"]

    hourly_times = hourly.get("time", [])
    hourly_rain = hourly.get("rain", [])
    hourly_showers = hourly.get("showers", [])
    hourly_prob = hourly.get("precipitation_probability", [])

    result = f"🌍 **Прогноз погоды для {city} (ECMWF IFS HRES)**\n\n"

    for i, day_time in enumerate(daily_times):
        day_date = datetime.fromisoformat(day_time)
        day_name = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"][day_date.weekday()]

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
                total_precip = rain_val + showers_val
                if total_precip > 0.1 or prob_val > 30:
                    hour_str = hour_time.split("T")[1][:5]  # "HH:MM"
                    rain_hours.append((j, hour_str))

        # Группируем последовательные часы в интервалы
        intervals = []
        if rain_hours:
            current = [rain_hours[0][1]]
            for k in range(1, len(rain_hours)):
                # Если следующий час идёт подряд (индекс +1)
                if rain_hours[k][0] == rain_hours[k - 1][0] + 1:
                    current.append(rain_hours[k][1])
                else:
                    intervals.append(current)
                    current = [rain_hours[k][1]]
            intervals.append(current)

        # Формируем описание осадков
        if not intervals:
            rain_desc = "Осадков не ожидается"
        else:
            parts = []
            for interval in intervals:
                start = interval[0]
                end = interval[-1]
                duration = len(interval)
                if start == end:
                    parts.append(f"в {start}")
                else:
                    parts.append(f"с {start} до {end} ({duration} ч)")
            rain_desc = "Дождь: " + ", ".join(parts)

        result += f"**{day_name}, {day_time}**\n"
        result += f"🌡 **Температура:** min{temp_min:.1f}°C… max{temp_max:.1f}°C\n"
        result += f"💨 **Ветер (макс.):** {wind_max:.1f} км/ч\n"
        result += f"☔️ **Осадки:** {rain_desc}\n"
        result += "────────────────────\n"

    return result


def format_hourly_forecast(data: dict, forecast_type: str) -> str:
    """Форматирует почасовой прогноз на сегодня или завтра"""
    city = data["city_info"]["name"]
    hourly = data["hourly"]
    times = hourly["time"]

    # Определяем, сегодня или завтра
    if forecast_type == "forecast_today":
        day_label = "сегодня"
    else:
        day_label = "завтра"

    # Группируем часы по 3 часа (интервалы 00-03, 03-06, ..., 21-00)
    intervals = []
    for start_hour in range(0, 24, 3):
        end_hour = (start_hour + 3) % 24
        intervals.append((start_hour, end_hour))

    result = f"🌍 **Прогноз погоды для {city} ({day_label})**\n"
    result += "ECMWF IFS HRES (9 км)\n"
    result += "⏱ Интервалы по 3 часа\n\n"

    for start_h, end_h in intervals:
        # Собираем данные для часов, попадающих в интервал [start_h, start_h+3)
        temps = []
        winds = []
        probs = []
        total_precip = 0.0
        count = 0

        for i, time in enumerate(times):
            dt = datetime.fromisoformat(time)
            hour = dt.hour
            # Проверяем, что час в нужном интервале
            if start_h <= hour < start_h + 3:
                temps.append(hourly["temperature_2m"][i])
                winds.append(hourly["wind_speed_10m"][i])
                probs.append(hourly["precipitation_probability"][i])
                rain = hourly.get("rain", [0])[i] if i < len(hourly.get("rain", [])) else 0
                showers = hourly.get("showers", [0])[i] if i < len(hourly.get("showers", [])) else 0
                total_precip += rain + showers
                count += 1

        if count == 0:
            continue  # нет данных для этого интервала (например, завтра после 21:00)

        avg_temp = sum(temps) / count
        avg_wind = sum(winds) / count
        max_prob = max(probs) if probs else 0

        # Формируем строку интервала
        interval_str = f"{start_h:02d}:00–{end_h:02d}:00"
        result += f"**{interval_str}** 🌡 {avg_temp:.1f}°C  💨 {avg_wind:.1f} км/ч\n"
        result += f"☔ {total_precip:.1f} мм осадков  (вероятность {max_prob:.0f}%)\n"
        result += "──────────────\n"

    return result