import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from handlers import router
from logger import setup_logger
from scheduler import setup_scheduler

logger = setup_logger()


async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    # Запуск планировщика
    setup_scheduler(bot)
    logger.info("Планировщик рассылок запущен")

    logger.info("Бот запущен")
    try:
        await dp.start_polling(bot)
    finally:
        logger.info("Бот остановлен")


if __name__ == "__main__":
    asyncio.run(main())
