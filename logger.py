import logging
from datetime import datetime
from pathlib import Path

# Пути к файлам логов (в папке с ботом)
LOG_FILE = Path(__file__).parent / "bot.log"
STATS_FILE = Path(__file__).parent / "users_stats.log"


# Настройка основного логгера для бота (error, info)
def setup_logger():
    logger = logging.getLogger("weather_bot")
    logger.setLevel(logging.INFO)

    # Если уже есть обработчики, не добавляем повторно
    if not logger.handlers:
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# Логирование статистики пользователей
def log_user_request(city: str, user_id: int, username: str = None):
    """Записывает информацию о запросе в users_stats.log"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    username_str = username if username else "None"
    with open(STATS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{city} | {now} | id{user_id} | @{username_str}\n")