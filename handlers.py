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
    times = daily["time"]

    result = f"🌍 **Прогноз погоды для {city} (ECMWF IFS HRES)**\n\n"

    for i, day_time in enumerate(times):
        # Определяем день недели
        day_date = datetime.fromisoformat(day_time)
        day_name = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"][day_date.weekday()]

        # Получаем данные
        temp_max = daily["temperature_2m_max"][i]
        temp_min = daily["temperature_2m_min"][i]
        wind_max = daily["wind_speed_10m_max"][i]

        result += f"**{day_name}, {day_time}**\n"
        result += f"🌡 **Температура:** от {temp_min:.1f}°C до {temp_max:.1f}°C\n"
        result += f"💨 **Ветер (макс.):** {wind_max:.1f} км/ч\n"

        # Анализ осадков
        rain_info = "Нет"
        rain_details = []

        # Проверяем часовые данные для осадков
        hourly = data.get("hourly", {})
        if hourly and "time" in hourly:
            for j, hour_time in enumerate(hourly["time"]):
                if hour_time.startswith(day_time.split("T")[0]):  # Только текущий день
                    rain_val = hourly.get("rain", [0])[j] if j < len(hourly.get("rain", [])) else 0
                    showers_val = hourly.get("showers", [0])[j] if j < len(hourly.get("showers", [])) else 0
                    precip_prob = hourly.get("precipitation_probability", [0])[j] if j < len(
                        hourly.get("precipitation_probability", [])) else 0

                    total_precip = rain_val + showers_val
                    if total_precip > 0 or precip_prob > 20:
                        hour = hour_time.split("T")[1][:5]
                        rain_details.append(f"{hour}: {total_precip:.1f} мм (вер. {precip_prob:.0f}%)")

        if rain_details:
            rain_info = "Возможен дождь:\n" + "\n".join(rain_details[:3])  # Ограничим 3 часами

        result += f"☔️ **Осадки:** {rain_info}\n"
        result += "─" * 20 + "\n"

    return result


def format_hourly_forecast(data: dict, forecast_type: str) -> str:
    """Форматирует почасовой прогноз на сегодня или завтра"""
    city = data["city_info"]["name"]
    hourly = data["hourly"]
    times = hourly["time"]

    day_label = "сегодня" if forecast_type == "forecast_today" else "завтра"
    result = f"🌍 **Почасовой прогноз для {city} ({day_label})**\n\n"
    result += "ECMWF IFS HRES | ⏱ в формате 'чаc:мин'\n\n"

    for i, time in enumerate(times):
        dt = datetime.fromisoformat(time)
        hour = dt.strftime("%H:%M")

        temp = hourly["temperature_2m"][i]
        wind = hourly["wind_speed_10m"][i]
        precip_prob = hourly["precipitation_probability"][i]
        rain = hourly.get("rain", [0])[i] if i < len(hourly.get("rain", [])) else 0
        showers = hourly.get("showers", [0])[i] if i < len(hourly.get("showers", [])) else 0
        total_precip = rain + showers

        result += f"**{hour}** 🌡 {temp:.1f}°C | 💨 {wind:.1f} км/ч\n"
        result += f"☔️ **{total_precip:.1f} мм** (вер. {precip_prob:.0f}%)\n"
        result += "─" * 15 + "\n"

    return result