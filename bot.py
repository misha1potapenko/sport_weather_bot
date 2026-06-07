import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import ClientTimeout
from aiogram.client.session.aiohttp import AiohttpSession


from config import BOT_TOKEN
from handlers import router

# Настройка логирования для отслеживания работы бота
logging.basicConfig(level=logging.INFO)


async def main():
    # Инициализация бота и диспетчера с хранилищем состояний в памяти
    # Увеличиваем таймаут до 60 секунд
    session = AiohttpSession(timeout=60)
    bot = Bot(token=BOT_TOKEN, session=session)
    dp = Dispatcher(storage=MemoryStorage())

    # Подключаем роутер с обработчиками
    dp.include_router(router)

    # Запускаем бота
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())