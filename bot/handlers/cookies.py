import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.config import admin_id_set, settings
from bot.services.cookies import cookies_configured, cookies_file, sync_cookies_to_vidbee
from bot.services.vidbee import VidBeeClient

router = Router()
logger = logging.getLogger(__name__)


def _is_admin(user_id: int) -> bool:
    admins = admin_id_set()
    return not admins or user_id in admins


COOKIES_HELP = (
    "<b>Instagram cookies</b>\n\n"
    "Instagram требует cookies для скачивания с сервера.\n\n"
    "<b>Способ 1 — файл на сервере</b>\n"
    f"Положите <code>cookies.txt</code> в папку <code>cookies/</code> проекта "
    "и перезапустите: <code>docker compose restart bot worker vidbee-api</code>\n\n"
    "<b>Способ 2 — через бота (админ)</b>\n"
    "Отправьте файл <code>cookies.txt</code> как документ.\n\n"
    "<b>Как получить cookies.txt</b>\n"
    "1. Установите расширение «Get cookies.txt LOCALLY» в Chrome/Firefox\n"
    "2. Зайдите на instagram.com под своим аккаунтом\n"
    "3. Экспортируйте cookies для instagram.com\n"
    "4. Отправьте файл боту или скопируйте в <code>cookies/cookies.txt</code>\n\n"
    "Команды:\n"
    "/cookies — эта справка\n"
    "/cookies_status — проверить, загружены ли cookies"
)


@router.message(Command("cookies"))
async def cmd_cookies(message: Message) -> None:
    await message.answer(COOKIES_HELP)


@router.message(Command("cookies_status"))
async def cmd_cookies_status(message: Message) -> None:
    path = cookies_file()
    if cookies_configured():
        await message.answer(f"✅ Cookies настроены: <code>{path}</code>")
        return
    if path.is_file():
        await message.answer(
            "⚠️ Файл cookies найден, но не содержит instagram.com cookies.\n"
            "Экспортируйте cookies именно с instagram.com"
        )
        return
    await message.answer(
        "❌ Cookies не настроены.\n\n"
        "Instagram не будет работать без cookies.txt.\n"
        "Используйте /cookies для инструкции."
    )


@router.message(F.document)
async def handle_cookies_upload(message: Message) -> None:
    if not message.from_user or not message.document:
        return

    if not _is_admin(message.from_user.id):
        return

    filename = (message.document.file_name or "").lower()
    if filename != "cookies.txt":
        return

    if not message.bot:
        return

    path = cookies_file()
    path.parent.mkdir(parents=True, exist_ok=True)

    await message.bot.download(message.document, destination=path)

    if not cookies_configured():
        await message.answer(
            "⚠️ Файл сохранён, но instagram.com cookies не найдены.\n"
            "Убедитесь, что экспортировали cookies с instagram.com"
        )
        return

    if await sync_cookies_to_vidbee():
        await message.answer("✅ Cookies загружены и применены. Можно скачивать Instagram.")
    else:
        await message.answer("❌ Файл сохранён, но не удалось синхронизировать с VidBee.")
