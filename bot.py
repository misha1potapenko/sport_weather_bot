import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.session.aiohttp import AiohttpSession

from config import BOT_TOKEN
from handlers import router
from logger import setup_logger
from scheduler import setup_scheduler

logger = setup_logger()


async def main():
    # Создаём сессию с увеличенным таймаутом
    session = AiohttpSession(timeout=60)
    bot = Bot(token=BOT_TOKEN, session=session)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    setup_scheduler(bot)
    logger.info("Планировщик рассылок запущен")

    logger.info("Бот запущен")
    try:
        await dp.start_polling(bot)
    finally:
        logger.info("Бот остановлен")


if __name__ == "__main__":
    asyncio.run(main())