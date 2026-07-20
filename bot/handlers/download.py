import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.config import settings
from bot.db.session import get_session
from bot.keyboards.formats import format_keyboard
from bot.services.access_facade import check_download_access
from bot.services.download_logs import start_download_log
from bot.services.jobs import (
    DownloadJob,
    PendingDownload,
    clear_active,
    clear_pending,
    enqueue_download,
    get_active_task_id,
    load_pending,
    save_pending,
    set_active,
)
from bot.services.cookies_manager import is_url_ready
from bot.services.users import upsert_user
from bot.services.vidbee import VidBeeClient, VidBeeError, humanize_error
from bot.utils.formats import (
    FORMAT_MAP,
    FormatChoice,
    estimate_best_size_mb,
    format_duration,
    format_size_mb,
)
from bot.utils.urls import URL_PATTERN, extract_urls

router = Router()
logger = logging.getLogger(__name__)

vidbee = VidBeeClient()


async def _ensure_download_allowed(message: Message, user_id: int, chat_id: int) -> bool:
    async with get_session() as session:
        access = await check_download_access(session, user_id, chat_id)
    if access.allowed:
        return True
    await message.answer(
        f"📊 Сегодня использовано: <b>{access.limit}/{access.limit}</b> загрузок\n\n"
        "⭐ Premium — безлимит. /premium"
    )
    return False


def _should_auto_download(duration: int | None, size_mb: float | None) -> bool:
    if duration is not None and duration > settings.auto_max_duration_sec:
        return False
    if size_mb is not None and size_mb > settings.auto_max_size_mb:
        return False
    return True


def _info_text(title: str, duration: int | None, size_mb: float | None, uploader: str | None) -> str:
    lines = [
        f"🎬 <b>{title}</b>",
        f"⏱ Длительность: {format_duration(duration)}",
        f"📦 Примерный размер: {format_size_mb(size_mb)}",
    ]
    if uploader:
        lines.append(f"👤 {uploader}")
    lines.append("\nВыберите формат:")
    return "\n".join(lines)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message) -> None:
    if not message.from_user:
        return

    user_id = message.from_user.id
    task_id = await get_active_task_id(user_id)

    if not task_id or task_id == "pending":
        await clear_active(user_id)
        await message.answer("Нет активной загрузки.")
        return

    try:
        cancelled = await vidbee.cancel_download(task_id)
    except VidBeeError as exc:
        await message.answer(f"❌ {humanize_error(exc.category, str(exc))}")
        return

    await clear_active(user_id)

    if cancelled:
        await message.answer("✅ Загрузка отменена.")
    else:
        await message.answer("Загрузка уже завершена или не найдена.")


@router.message(F.text.regexp(URL_PATTERN))
async def handle_url(message: Message) -> None:
    if not message.text or not message.from_user:
        return

    url = extract_urls(message.text)[0]
    user_id = message.from_user.id

    ready, platform, hint = is_url_ready(url)
    if not ready and platform:
        await message.answer(
            f"❌ <b>{platform.name}</b> требует авторизацию (cookies).\n\n"
            f"{hint or ''}\n\n"
            "Загрузите cookies в web-админке → Сервисы или через /cookies"
        )
        return

    async with get_session() as session:
        await upsert_user(
            session,
            user_id,
            message.from_user.username,
            message.from_user.first_name,
        )

    if not await _ensure_download_allowed(message, user_id, message.chat.id):
        return

    status_msg = await message.answer("🔍 Получаю информацию о видео...")

    try:
        info = await vidbee.get_video_info(url)
    except VidBeeError as exc:
        await status_msg.edit_text(f"❌ {humanize_error(exc.category, str(exc))}")
        return
    except Exception:
        logger.exception("Failed to get video info for %s", url)
        await status_msg.edit_text("❌ Не удалось получить информацию о видео.")
        return

    size_mb = estimate_best_size_mb(info.formats)

    if _should_auto_download(info.duration, size_mb):
        await status_msg.edit_text(f"⬇️ Скачиваю: <b>{info.title}</b>\n\n0%")
        fmt = FORMAT_MAP[FormatChoice.AUTO]
        async with get_session() as session:
            log = await start_download_log(session, user_id, url, FormatChoice.AUTO.value)
            log_id = log.id
        job = DownloadJob(
            user_id=user_id,
            chat_id=message.chat.id,
            message_id=status_msg.message_id,
            url=url,
            title=info.title,
            duration=info.duration,
            thumbnail=info.thumbnail,
            format_choice=FormatChoice.AUTO.value,
            download_type=fmt.download_type,
            format_string=fmt.format_string,
            container=fmt.container,
            log_id=log_id,
        )
        if not await set_active(user_id, "pending"):
            await status_msg.edit_text(
                "⏳ У вас уже есть активная загрузка. Дождитесь завершения или /cancel"
            )
            return
        job_id = await enqueue_download(job)
        if not job_id:
            await clear_active(user_id)
            await status_msg.edit_text("❌ Не удалось поставить задачу в очередь.")
        return

    pending = PendingDownload(
        url=url,
        title=info.title,
        duration=info.duration,
        thumbnail=info.thumbnail,
        uploader=info.uploader,
        chat_id=message.chat.id,
        message_id=status_msg.message_id,
    )
    await save_pending(user_id, pending)

    text = _info_text(info.title, info.duration, size_mb, info.uploader)
    await status_msg.edit_text(text, reply_markup=format_keyboard())


@router.callback_query(F.data.startswith("fmt:"))
async def handle_format_choice(callback: CallbackQuery) -> None:
    if not callback.from_user or not callback.message:
        await callback.answer()
        return

    choice_raw = callback.data.removeprefix("fmt:")
    user_id = callback.from_user.id

    if choice_raw == "cancel":
        await clear_pending(user_id)
        await callback.message.edit_text("❌ Отменено.")
        await callback.answer()
        return

    try:
        format_choice = FormatChoice(choice_raw)
    except ValueError:
        await callback.answer("Неизвестный формат", show_alert=True)
        return

    pending = await load_pending(user_id)
    if not pending:
        await callback.answer("Сессия истекла. Отправьте ссылку снова.", show_alert=True)
        return

    if not callback.message:
        await callback.answer()
        return
    if not await _ensure_download_allowed(callback.message, user_id, callback.message.chat.id):
        await callback.answer("Достигнут дневной лимит", show_alert=True)
        return

    await clear_pending(user_id)
    await callback.answer()

    fmt = FORMAT_MAP[format_choice]
    async with get_session() as session:
        log = await start_download_log(session, user_id, pending.url, format_choice.value)
        log_id = log.id
    job = DownloadJob(
        user_id=user_id,
        chat_id=pending.chat_id,
        message_id=pending.message_id,
        url=pending.url,
        title=pending.title,
        duration=pending.duration,
        thumbnail=pending.thumbnail,
        format_choice=format_choice.value,
        download_type=fmt.download_type,
        format_string=fmt.format_string,
        container=fmt.container,
        log_id=log_id,
    )

    if not await set_active(user_id, "pending"):
        await callback.message.edit_text(
            "⏳ У вас уже есть активная загрузка. Дождитесь завершения или /cancel"
        )
        return

    job_id = await enqueue_download(job)
    if not job_id:
        await clear_active(user_id)
        await callback.message.edit_text("❌ Не удалось поставить задачу в очередь.")
        return

    await callback.message.edit_text(f"⬇️ Загрузка: <b>{pending.title}</b>\n\n0%")

