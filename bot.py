import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from handlers import router

# Настройка логирования для отслеживания работы бота
logging.basicConfig(level=logging.INFO)


async def main():
    # Инициализация бота и диспетчера с хранилищем состояний в памяти
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Подключаем роутер с обработчиками
    dp.include_router(router)

    # Запускаем бота
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())