import asyncio
import logging

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.handlers import admin, cookies, download, feedback, start
from bot.middleware.access import AccessMiddleware
from bot.services.cookies import cookies_configured, sync_cookies_to_vidbee
from bot.services.telegram_files import create_bot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    bot = create_bot()

    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(AccessMiddleware())
    dp.callback_query.middleware(AccessMiddleware())
    dp.include_router(feedback.router)
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(cookies.router)
    dp.include_router(download.router)

    if await sync_cookies_to_vidbee():
        logger.info("Instagram cookies synced on startup")
    elif cookies_configured():
        logger.warning("Cookies file exists but sync failed")
    else:
        logger.warning("Instagram cookies not configured — see /cookies")

    logger.info("Starting vdown bot...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
