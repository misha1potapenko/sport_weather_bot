import json
import os
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot

from weather_api import get_weather_forecast
from formatters import format_hourly_forecast, format_weekly_forecast, send_long_message

scheduler = AsyncIOScheduler()

async def send_forecast_to_user(bot: Bot, user_id: int, city: str, forecast_type: str):
    """Отправляет прогноз пользователю по расписанию."""
    try:
        data = await get_weather_forecast(city, forecast_type)
        if "error" in data:
            await bot.send_message(user_id, f"Ошибка получения прогноза для {city}: {data['error']}")
            return
        if forecast_type == "weekly":
            text = format_weekly_forecast(data)
        else:
            day_label = "сегодня" if forecast_type == "today" else "завтра"
            text = format_hourly_forecast(data, day_label)
        await send_long_message(bot, user_id, text)
    except Exception as e:
        await bot.send_message(user_id, f"Произошла ошибка при отправке прогноза. Попробуйте позже.")
        # Записываем ошибку в лог (можно в bot.log)
        print(f"Ошибка отправки прогноза пользователю {user_id}: {e}")

async def check_subscriptions(bot: Bot):
    """Проверяет, кому нужно отправить прогноз в текущий час."""
    subs_file = "subscriptions.json"
    if not os.path.exists(subs_file):
        return
    with open(subs_file, "r", encoding="utf-8") as f:
        subs = json.load(f)
    now = datetime.now()
    current_hour = now.hour
    current_minute = now.minute

    # Отправляем только в начале часа (0 минута)
    if current_minute != 0:
        return

    for user_id_str, sub in subs.items():
        user_id = int(user_id_str)
        if sub["hour"] == current_hour:
            city = sub["city"]
            forecast_type = sub["forecast_type"]  # "today" или "tomorrow"
            await send_forecast_to_user(bot, user_id, city, forecast_type)

def setup_scheduler(bot: Bot):
    """Запускает планировщик."""
    scheduler.add_job(
        check_subscriptions,
        CronTrigger(minute="*"),   # каждую минуту
        args=[bot],
        id="check_subscriptions"
    )
    scheduler.start()