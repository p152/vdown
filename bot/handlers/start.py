import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from bot.config import settings
from bot.db.session import get_session
from bot.services.users import upsert_user

router = Router()
logger = logging.getLogger(__name__)

START_TEXT = (
    "👋 <b>vdown</b> — бот для скачивания видео\n\n"
    "Отправьте ссылку на видео с YouTube, TikTok, Instagram, Twitter/X "
    "и 1000+ других сайтов.\n\n"
    "Короткие ролики скачиваются автоматически, для длинных — выберите формат.\n\n"
    f"🆓 Бесплатно: <b>{settings.free_daily_limit}</b> загрузок в день\n"
    "⭐ Premium — безлимит: /premium\n\n"
    "Команды:\n"
    "/help — справка\n"
    "/status — ваш лимит\n"
    "/premium — купить Premium\n"
    "/feedback — сообщить об ошибке\n"
    "/cancel — отменить загрузку"
)

HELP_TEXT = (
    "<b>Как пользоваться</b>\n\n"
    "1. Отправьте ссылку на видео\n"
    "2. Дождитесь загрузки или выберите формат\n"
    "3. Получите файл в чат\n\n"
    "<b>Поддерживаемые сервисы</b>\n"
    "YouTube, TikTok, Instagram, Twitter/X, VK, Reddit и 1000+ сайтов "
    "(через yt-dlp / VidBee).\n\n"
    "<b>Лимиты</b>\n"
    "• Бесплатно: несколько загрузок в день (/status)\n"
    "• Premium: безлимит (/premium)\n"
    "• Максимальный размер файла: до 2 ГБ (local Bot API)\n"
    "• Одна активная загрузка на пользователя\n\n"
    "<b>Команды</b>\n"
    "/status — ваш лимит / Premium\n"
    "/premium — купить Premium\n"
    "/feedback — сообщить об ошибке\n"
    "/cancel — отменить текущую загрузку"
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    if message.from_user:
        async with get_session() as session:
            await upsert_user(
                session,
                message.from_user.id,
                message.from_user.username,
                message.from_user.first_name,
            )
    await message.answer(START_TEXT)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)
