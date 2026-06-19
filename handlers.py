from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from keyboards import get_main_reply_keyboard
from weather_api import get_weather_forecast
from formatters import safe_send, format_hourly_forecast, format_weekly_forecast
from logger import log_user_request

import json
import os

router = Router()


class WeatherState(StatesGroup):
    waiting_city = State()  # для прогноза и для рассылки (различаем по флагу)


# ------------------------------------------------------------
# Команда /start
# ------------------------------------------------------------
@router.message(CommandStart())
async def start_command(message: Message):
    await message.answer(
        "Привет! Я бот прогноза погоды.\n"
        "Использую модель ECMWF IFS HRES.\n\n"
        "Нажми на одну из кнопок внизу, затем напиши название города.",
        reply_markup=get_main_reply_keyboard()
    )


# ------------------------------------------------------------
# Обработка нажатий на кнопки прогнозов (сегодня, завтра, неделя)
# ------------------------------------------------------------
@router.message(F.text.in_(["🌤 Прогноз на сегодня", "⛅ Прогноз на завтра", "📅 Прогноз на неделю"]))
async def forecast_button_handler(message: Message, state: FSMContext):
    text = message.text
    if text == "🌤 Прогноз на сегодня":
        forecast_type = "today"
        day_label = "сегодня"
    elif text == "⛅ Прогноз на завтра":
        forecast_type = "tomorrow"
        day_label = "завтра"
    else:
        forecast_type = "weekly"
        day_label = None

    # Сохраняем, что это запрос прогноза (не рассылка)
    await state.update_data(forecast_type=forecast_type, day_label=day_label, subscription=False)
    await state.set_state(WeatherState.waiting_city)
    await message.answer("Введите название города:")


# ------------------------------------------------------------
# Обработка кнопки "Настроить рассылку"
# ------------------------------------------------------------
@router.message(F.text == "⏰ Настроить рассылку")
async def subscription_button_handler(message: Message, state: FSMContext):
    # Сохраняем, что это настройка рассылки
    await state.update_data(subscription=True)
    await state.set_state(WeatherState.waiting_city)
    await message.answer(
        "Настройка ежедневной рассылки прогноза.\n"
        "Введите название вашего города (например, Москва):"
    )


# ------------------------------------------------------------
# Обработка ввода города (общий для прогноза и рассылки)
# ------------------------------------------------------------
@router.message(WeatherState.waiting_city, F.text)
async def process_city_input(message: Message, state: FSMContext):
    city = message.text.strip()
    if len(city) < 2:
        await message.answer("Слишком короткое название. Введите полное название города.")
        return

    data = await state.get_data()
    is_subscription = data.get("subscription", False)

    if is_subscription:
        # --- Логика настройки рассылки ---
        # Сохраняем город и запрашиваем день прогноза (сегодня/завтра)
        await state.update_data(city=city)
        # Создаём инлайн-кнопки для выбора дня
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌅 Сегодня (утро)", callback_data="sub_today")],
            [InlineKeyboardButton(text="🌇 Завтра (вечер)", callback_data="sub_tomorrow")]
        ])
        await message.answer("Выберите, прогноз на какой день вы хотите получать:", reply_markup=kb)
        # Устанавливаем новое состояние для выбора дня (чтобы не путать с вводом города)
        # Можно использовать то же состояние, но мы перейдём в новое состояние для дня
        from aiogram.fsm.state import State
        class SubState(StatesGroup):
            waiting_day = State()

        # Но проще сохранить в data и использовать отдельный обработчик callback
        # Мы обработаем callback ниже
        # Пока просто сохраняем город и ждём callback
        return
    else:
        # --- Логика обычного прогноза ---
        forecast_type = data.get("forecast_type")
        day_label = data.get("day_label")
        if not forecast_type:
            await message.answer("Произошла ошибка. Нажмите кнопку заново.")
            await state.clear()
            return

        processing = await message.answer("⏳ Получаю данные с Open-Meteo...")
        forecast_data = await get_weather_forecast(city, forecast_type)
        await processing.delete()

        if "error" in forecast_data:
            await message.answer(f"Ошибка: {forecast_data['error']}\nПопробуйте другой город или /start.")
            await state.clear()
            return

        # Логируем запрос пользователя
        username = message.from_user.username
        log_user_request(city, message.from_user.id, username)

        if forecast_type == "weekly":
            response = format_weekly_forecast(forecast_data)
        else:
            response = format_hourly_forecast(forecast_data, day_label)

        await safe_send(message, response)
        await state.clear()
        await message.answer("Выберите другую кнопку внизу.", reply_markup=get_main_reply_keyboard())


# ------------------------------------------------------------
# Обработка callback для выбора дня рассылки (sub_today / sub_tomorrow)
# ------------------------------------------------------------
@router.callback_query(F.data.startswith("sub_"))
async def subscription_day_callback(callback: CallbackQuery, state: FSMContext):
    forecast_type = "today" if callback.data == "sub_today" else "tomorrow"
    await state.update_data(forecast_type=forecast_type)

    # Получаем город из состояния
    data = await state.get_data()
    city = data.get("city")
    if not city:
        await callback.message.answer("Ошибка: город не найден. Начните заново с кнопки 'Настроить рассылку'.")
        await state.clear()
        await callback.answer()
        return

    # Предлагаем выбрать час (утро для today, вечер для tomorrow)
    if forecast_type == "today":
        hours = list(range(6, 12))  # 6-11
        label = "утром"
    else:
        hours = list(range(18, 24))  # 18-23
        label = "вечером"

    # Клавиатура с часами
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    buttons = [[KeyboardButton(text=f"{h}:00")] for h in hours]
    kb = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)
    await callback.message.answer(
        f"Вы выбрали прогноз на {forecast_type} ({label}).\n"
        "Выберите час, в который вам удобно получать прогноз:",
        reply_markup=kb
    )
    # Переходим в состояние ожидания часа (можно использовать то же или новое)
    # Для простоты используем то же состояние, но добавим флаг ожидания часа
    await state.update_data(waiting_hour=True)
    await callback.answer()


# ------------------------------------------------------------
# Обработка выбора часа (для рассылки)
# ------------------------------------------------------------
@router.message(WeatherState.waiting_city, F.text)
async def process_subscription_hour(message: Message, state: FSMContext):
    # Проверяем, что мы действительно ждём час (флаг waiting_hour)
    data = await state.get_data()
    if not data.get("waiting_hour"):
        # Если не ждём час, то этот обработчик не должен сработать, но на всякий случай пропускаем
        return

    hour_text = message.text.strip()
    if not hour_text.endswith(":00") or not hour_text[:-3].isdigit():
        await message.answer("Пожалуйста, выберите час из предложенных кнопок.")
        return

    hour = int(hour_text.split(":")[0])
    # Сохраняем подписку
    user_id = message.from_user.id
    city = data.get("city")
    forecast_type = data.get("forecast_type")

    if not city or not forecast_type:
        await message.answer("Ошибка данных. Начните настройку заново.")
        await state.clear()
        return

    sub = {
        "city": city,
        "forecast_type": forecast_type,
        "hour": hour
    }
    # Загружаем существующие подписки
    subs = {}
    if os.path.exists("subscriptions.json"):
        with open("subscriptions.json", "r", encoding="utf-8") as f:
            subs = json.load(f)
    subs[str(user_id)] = sub
    with open("subscriptions.json", "w", encoding="utf-8") as f:
        json.dump(subs, f, indent=2, ensure_ascii=False)

    await state.clear()
    await message.answer(
        f"✅ Рассылка настроена!\n"
        f"Город: {city}\n"
        f"Прогноз: {'на сегодня (утром)' if forecast_type == 'today' else 'на завтра (вечером)'}\n"
        f"Время: {hour}:00\n\n"
        "Вы можете изменить настройки, снова нажав 'Настроить рассылку'.",
        reply_markup=get_main_reply_keyboard()
    )


# ------------------------------------------------------------
# Обработка простого текстового ввода (без кнопок) - даём прогноз на неделю
# ------------------------------------------------------------
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
    # Логируем запрос
    username = message.from_user.username
    log_user_request(city, message.from_user.id, username)
    response = format_weekly_forecast(forecast_data)
    await safe_send(message, response)