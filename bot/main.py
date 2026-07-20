import asyncio
import logging

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.db.session import get_session, init_db
from bot.handlers import admin, cookies, download, feedback, premium, start
from bot.middleware.access import AccessMiddleware
from bot.services.cookies_manager import sync_cookies_to_vidbee
from bot.services.settings_store import seed_defaults
from bot.services.telegram_files import create_bot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    await init_db()
    async with get_session() as session:
        await seed_defaults(session)

    bot = create_bot()

    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(AccessMiddleware())
    dp.callback_query.middleware(AccessMiddleware())
    dp.include_router(premium.router)
    dp.include_router(feedback.router)
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(cookies.router)
    dp.include_router(download.router)

    if await sync_cookies_to_vidbee():
        logger.info("Cookies synced to VidBee on startup")
    else:
        logger.warning("Platform cookies not fully configured — see /cookies or admin → Сервисы")

    logger.info("Starting vdown bot...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
