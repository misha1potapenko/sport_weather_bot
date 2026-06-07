from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from keyboards import get_main_keyboard
from weather_api import get_weather_forecast

router = Router()


# ---------------------- Состояния ----------------------
class WeatherStates(StatesGroup):
    waiting_for_city = State()


# ---------------------- Вспомогательная функция для длинных сообщений ----------------------
async def safe_send(message: Message, text: str):
    if len(text) > 4096:
        for x in range(0, len(text), 4096):
            await message.answer(text[x:x + 4096])
    else:
        await message.answer(text)


# ---------------------- Форматирование прогноза на 3 дня (с интервалами дождя) ----------------------
def format_daily_forecast(data: dict) -> str:
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
                    hour_str = hour_time.split("T")[1][:5]
                    rain_hours.append((j, hour_str))

        # Группировка последовательных часов
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
        result += f"🌡 **Температура:** {temp_min:.1f}°C…{temp_max:.1f}°C\n"
        result += f"💨 **Ветер (макс.):** {wind_max:.1f} км/ч\n"
        result += f"☔️ **Осадки:** {rain_desc}\n"
        result += "────────────────────\n"

    return result


# ---------------------- Почасовой прогноз с интервалом 3 часа ----------------------
def format_hourly_forecast(data: dict, forecast_type: str) -> str:
    city = data["city_info"]["name"]
    hourly = data["hourly"]
    times = hourly["time"]

    day_label = "сегодня" if forecast_type == "forecast_today" else "завтра"

    # Группировка по 3 часа
    intervals = []
    for start_hour in range(0, 24, 3):
        end_hour = start_hour + 3
        intervals.append((start_hour, end_hour))

    result = f"🌍 **Прогноз погоды для {city} ({day_label})**\n"
    result += "ECMWF IFS HRES (9 км)\n"
    result += "⏱ Интервалы по 3 часа\n\n"

    for start_h, end_h in intervals:
        temps = []
        winds = []
        probs = []
        total_precip = 0.0
        count = 0

        for i, time in enumerate(times):
            dt = datetime.fromisoformat(time)
            hour = dt.hour
            if start_h <= hour < end_h:
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

        interval_str = f"{start_h:02d}:00–{end_h:02d}:00"
        result += f"**{interval_str}** 🌡 {avg_temp:.1f}°C  💨 {avg_wind:.1f} км/ч\n"
        result += f"☔ {total_precip:.1f} мм осадков  (вероятность {max_prob:.0f}%)\n"
        result += "──────────────\n"

    return result


# ---------------------- Команда /start (удаляет старую Reply-клавиатуру) ----------------------
@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext):
    await state.clear()
    # Сначала убираем старую Reply-клавиатуру (если есть)
    await message.answer(
        "Обновляем меню...",
        reply_markup=ReplyKeyboardRemove()
    )
    # Затем отправляем приветствие с Inline-кнопками
    await message.answer(
        "Привет! Я бот прогноза погоды 🌤\n"
        "Я использую самую точную модель ECMWF IFS HRES от Open-Meteo.\n\n"
        "Вы можете:\n"
        "• Нажать на кнопки ниже\n"
        "• Написать название города (например, `Москва`)\n"
        "• Использовать команду `/weather Москва`\n\n"
        "Сразу получите прогноз на 3 дня!",
        reply_markup=get_main_keyboard()
    )


# ---------------------- Обработка нажатий на инлайн-кнопки ----------------------
@router.callback_query(F.data.in_(["forecast_3days", "forecast_today", "forecast_tomorrow"]))
async def ask_city(callback: CallbackQuery, state: FSMContext):
    await state.update_data(forecast_type=callback.data)
    await callback.message.answer("Введите название города:")
    await state.set_state(WeatherStates.waiting_for_city)
    await callback.answer()


# ---------------------- Обработка ввода города (после кнопки) ----------------------
@router.message(WeatherStates.waiting_for_city)
async def process_city(message: Message, state: FSMContext):
    city_name = message.text.strip()
    user_data = await state.get_data()
    forecast_type = user_data.get("forecast_type")

    if not forecast_type:
        await message.answer("Пожалуйста, начните заново через /start")
        await state.clear()
        return

    processing_msg = await message.answer("⏳ Получаю данные с Open-Meteo ECMWF IFS HRES...")

    if forecast_type == "forecast_3days":
        api_type = "3days"
    elif forecast_type == "forecast_today":
        api_type = "today"
    else:
        api_type = "tomorrow"

    forecast_data = await get_weather_forecast(city_name, api_type)
    await processing_msg.delete()

    if "error" in forecast_data:
        await message.answer(f"❌ Ошибка: {forecast_data['error']}\nПопробуйте другой город или используйте кнопки.")
        await state.clear()
        return

    if forecast_type == "forecast_3days":
        response_text = format_daily_forecast(forecast_data)
    else:
        response_text = format_hourly_forecast(forecast_data, forecast_type)

    await safe_send(message, response_text)
    await state.clear()
    await message.answer("Что ещё вас интересует?", reply_markup=get_main_keyboard())


# ---------------------- Команда /weather ----------------------
@router.message(Command("weather"))
async def weather_command(message: Message, command: Command):
    city = command.args
    if not city:
        await message.answer("Пожалуйста, укажите город после команды.\nПример: `/weather Москва`",
                             parse_mode="Markdown")
        return

    processing_msg = await message.answer("⏳ Получаю прогноз на 3 дня...")
    forecast_data = await get_weather_forecast(city.strip(), "3days")
    await processing_msg.delete()

    if "error" in forecast_data:
        await message.answer(f"❌ {forecast_data['error']}\nПопробуйте другой город или используйте кнопки.")
        return

    response_text = format_daily_forecast(forecast_data)
    await safe_send(message, response_text)


# ---------------------- Простой текстовый ввод (без состояния) ----------------------
@router.message(F.text, ~F.text.startswith('/'), StateFilter(None))
async def text_city_handler(message: Message):
    city = message.text.strip()
    if len(city) < 2:
        await message.answer("Слишком короткое название. Введите полное название города.")
        return

    processing_msg = await message.answer("⏳ Получаю прогноз на 3 дня...")
    forecast_data = await get_weather_forecast(city, "3days")
    await processing_msg.delete()

    if "error" in forecast_data:
        await message.answer(f"❌ Город `{city}` не найден.\nПожалуйста, проверьте название или используйте кнопки.",
                             parse_mode="Markdown")
        return

    response_text = format_daily_forecast(forecast_data)
    await safe_send(message, response_text)