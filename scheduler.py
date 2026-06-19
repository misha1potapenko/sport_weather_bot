import json
import os
import asyncio
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot
from weather_api import get_weather_forecast
from handlers import format_hourly_forecast, format_weekly_forecast, safe_send
from formatters import safe_send, format_hourly_forecast, format_weekly_forecast

scheduler = AsyncIOScheduler()


async def send_forecast_to_user(bot: Bot, user_id: int, city: str, forecast_type: str):
    """Отправляет прогноз пользователю"""
    try:
        data = await get_weather_forecast(city, forecast_type)
        if "error" in data:
            await bot.send_message(user_id, f"Ошибка получения прогноза для {city}. Проверьте город.")
            return
        if forecast_type == "weekly":
            text = format_weekly_forecast(data)
        else:
            day_label = "сегодня" if forecast_type == "today" else "завтра"
            text = format_hourly_forecast(data, day_label)
        await safe_send(bot, user_id, text)
    except Exception as e:
        await bot.send_message(user_id, f"Произошла ошибка при отправке прогноза. Попробуйте позже.")


async def check_subscriptions(bot: Bot):
    """Проверяет, кому сейчас нужно отправить прогноз"""
    if not os.path.exists("subscriptions.json"):
        return
    with open("subscriptions.json", "r", encoding="utf-8") as f:
        subs = json.load(f)
    now = datetime.now()
    current_hour = now.hour
    current_minute = now.minute

    # Отправляем прогноз в начале часа (минута = 0)
    if current_minute != 0:
        return

    for user_id_str, sub in subs.items():
        user_id = int(user_id_str)
        if sub["hour"] == current_hour:
            city = sub["city"]
            forecast_type = sub["forecast_type"]  # "today" или "tomorrow"
            await send_forecast_to_user(bot, user_id, city, forecast_type)


def setup_scheduler(bot: Bot):
    """Запускает планировщик"""
    scheduler.add_job(
        check_subscriptions,
        CronTrigger(minute="*"),  # каждую минуту
        args=[bot],
        id="check_subscriptions"
    )
    scheduler.start()