import logging
from pathlib import Path

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import FSInputFile

from bot.config import settings
from bot.utils.formats import normalize_duration

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
    path = Path(file_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    duration = normalize_duration(duration)

    # Local Bot API reads files from disk; FSInputFile expects a real path, not file:// URI.
    upload_timeout = 600

    if download_type == "audio":
        await bot.send_audio(
            chat_id=chat_id,
            audio=FSInputFile(path, filename=path.name),
            title=title,
            duration=duration,
            request_timeout=upload_timeout,
        )
    else:
        thumb = None
        if thumbnail_path:
            thumb_path = Path(thumbnail_path).resolve()
            if thumb_path.is_file():
                thumb = FSInputFile(thumb_path, filename=thumb_path.name)

        await bot.send_video(
            chat_id=chat_id,
            video=FSInputFile(path, filename=path.name),
            caption=title,
            duration=duration,
            thumbnail=thumb,
            supports_streaming=True,
            request_timeout=upload_timeout,
        )


def cleanup_file(file_path: str) -> None:
    try:
        path = Path(file_path)
        if path.is_file():
            path.unlink()
            logger.info("Removed downloaded file: %s", file_path)
    except OSError as exc:
        logger.warning("Failed to remove file %s: %s", file_path, exc)
