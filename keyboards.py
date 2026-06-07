from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_main_keyboard() -> InlineKeyboardMarkup:
    """Главная клавиатура с основными кнопками"""
    builder = InlineKeyboardBuilder()

    builder.button(text="🌤 Прогноз на 3 дня", callback_data="forecast_3days")
    builder.button(text="⏰ Почасовой прогноз на сегодня", callback_data="forecast_today")
    builder.button(text="⏰ Почасовой прогноз на завтра", callback_data="forecast_tomorrow")

    builder.adjust(1)  # Располагаем кнопки в столбик
    return builder.as_markup()