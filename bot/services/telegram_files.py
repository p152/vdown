import logging
from pathlib import Path

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import FSInputFile

from bot.config import settings

logger = logging.getLogger(__name__)


def create_bot() -> Bot:
    session = AiohttpSession(
        api=TelegramAPIServer.from_base(settings.telegram_bot_api_url, is_local=True)
    )
    return Bot(
        token=settings.bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


async def send_media(
    bot: Bot,
    chat_id: int,
    file_path: str,
    *,
    download_type: str,
    title: str | None = None,
    duration: int | None = None,
    thumbnail_path: str | None = None,
) -> None:
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    local_uri = f"file://{path.resolve()}"

    if download_type == "audio":
        await bot.send_audio(
            chat_id=chat_id,
            audio=FSInputFile(local_uri),
            title=title,
            duration=duration,
        )
    else:
        thumb = FSInputFile(thumbnail_path) if thumbnail_path else None
        await bot.send_video(
            chat_id=chat_id,
            video=FSInputFile(local_uri),
            caption=title,
            duration=duration,
            thumbnail=thumb,
            supports_streaming=True,
        )


def cleanup_file(file_path: str) -> None:
    try:
        path = Path(file_path)
        if path.is_file():
            path.unlink()
            logger.info("Removed downloaded file: %s", file_path)
    except OSError as exc:
        logger.warning("Failed to remove file %s: %s", file_path, exc)
