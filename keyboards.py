from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_reply_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="🌤 Прогноз на сегодня")],
        [KeyboardButton(text="⛅ Прогноз на завтра")],
        [KeyboardButton(text="📅 Прогноз на неделю")],
        [KeyboardButton(text="⏰ Настроить рассылку")]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=False
    )