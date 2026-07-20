import logging
from io import BytesIO

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message, User

from bot.access import can_upload_cookies, is_admin
from bot.services.cookies_manager import (
    cookies_master_path,
    list_platform_statuses,
    save_platform_cookies,
)
from bot.services.platform_catalog import PLATFORMS

router = Router()
logger = logging.getLogger(__name__)


def _admin_only(user: User) -> bool:
    return is_admin(user.id)


def _cookies_help() -> str:
    lines = [
        "<b>Настройка сервисов (cookies)</b>\n",
        "Web-админка → <b>Сервисы</b> — основной способ загрузки.\n",
        "Через бота: отправьте <code>cookies.txt</code> как документ.\n",
        "<b>Как получить cookies.txt</b>",
        "1. Расширение «Get cookies.txt LOCALLY»",
        "2. Войдите на сайт и экспортируйте cookies",
        "3. Загрузите в админку или отправьте файл боту\n",
        "<b>Статус:</b>",
    ]
    for item in list_platform_statuses():
        if item["auth"] == "none":
            icon = "✅"
        elif item["status"] == "ready":
            icon = "✅"
        elif item["auth"] == "cookies":
            icon = "❌"
        else:
            icon = "⚠️"
        lines.append(f"{icon} {item['name']}")
    lines.append("\n/cookies_status — проверить (только админ)")
    return "\n".join(lines)


@router.message(Command("cookies"), F.from_user.func(_admin_only))
async def cmd_cookies(message: Message) -> None:
    await message.answer(_cookies_help())


@router.message(Command("cookies_status"), F.from_user.func(_admin_only))
async def cmd_cookies_status(message: Message) -> None:
    path = cookies_master_path()
    lines = ["<b>Статус сервисов</b>\n"]
    for item in list_platform_statuses():
        if item["auth"] == "none":
            status = "не требуется"
        elif item["configured"]:
            status = "✅ настроено"
        elif item["auth"] == "cookies":
            status = "❌ нужны cookies"
        else:
            status = "⚠️ опционально"
        lines.append(f"• <b>{item['name']}</b>: {status}")
    if path.is_file():
        lines.append(f"\nФайл: <code>{path}</code>")
    else:
        lines.append("\nОбщий cookies.txt ещё не создан.")
    await message.answer("\n".join(lines))


@router.message(F.document)
async def handle_cookies_upload(message: Message) -> None:
    if not message.from_user or not message.document:
        return

    if not can_upload_cookies(message.from_user.id):
        return

    filename = (message.document.file_name or "").lower()
    if filename != "cookies.txt":
        return

    if not message.bot:
        return

    buffer = BytesIO()
    await message.bot.download(message.document, destination=buffer)
    content = buffer.getvalue().decode("utf-8", errors="ignore")

    platform_id = "instagram"
    content_lower = content.lower()
    for platform in PLATFORMS:
        if platform.auth == "none":
            continue
        if any(d in content_lower for d in platform.domains):
            platform_id = platform.id
            break

    try:
        result = await save_platform_cookies(platform_id, content)
    except ValueError as exc:
        await message.answer(f"❌ {exc}")
        return

    if result.get("synced"):
        await message.answer(f"✅ Cookies для {platform_id} загружены и применены в VidBee.")
    else:
        await message.answer("⚠️ Файл сохранён, но синхронизация с VidBee не удалась.")
