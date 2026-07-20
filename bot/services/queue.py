import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from aiogram.exceptions import TelegramBadRequest

from arq.cron import cron

from bot.config import settings
from bot.db.session import get_session
from bot.services.access_check import has_unlimited_access
from bot.services.download_logs import finish_download_log
from bot.services.subscription import is_premium
from bot.services.usage import increment_usage
from bot.utils.formats import normalize_duration
from bot.services.cookies import sync_cookies_to_vidbee
from bot.services.jobs import clear_active, redis_settings
from bot.services.telegram_files import cleanup_file, create_bot, send_media
from bot.services.vidbee import VidBeeClient, VidBeeError, humanize_error

logger = logging.getLogger(__name__)

_progress_last_update: dict[str, float] = {}
PROGRESS_MIN_INTERVAL = 2.0


async def _update_progress_message(
    bot,
    chat_id: int,
    message_id: int,
    title: str,
    percent: float,
    speed: str | None,
    eta: str | None,
) -> None:
    key = f"{chat_id}:{message_id}"
    now = time.monotonic()
    if now - _progress_last_update.get(key, 0) < PROGRESS_MIN_INTERVAL and percent < 100:
        return
    _progress_last_update[key] = now

    lines = [f"⬇️ Загрузка: <b>{title}</b>", "", f"📊 {percent:.0f}%"]
    if speed:
        lines.append(f"⚡ {speed}")
    if eta:
        lines.append(f"⏳ ETA: {eta}")

    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="\n".join(lines),
        )
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            logger.debug("Progress update failed: %s", exc)


def _resolve_file_path(download_path: str | None, saved_file_name: str | None) -> str | None:
    if saved_file_name:
        if download_path:
            base = Path(download_path)
            if base.is_dir():
                candidate = base / saved_file_name
                if candidate.is_file():
                    return str(candidate)
            elif base.is_file():
                return str(base)
        candidate = Path(settings.downloads_dir) / saved_file_name
        if candidate.is_file():
            return str(candidate)
    if download_path and Path(download_path).is_file():
        return download_path
    return None


async def process_download(ctx: dict[str, Any], job_data: dict[str, Any]) -> dict[str, str]:
    """arq worker: download via VidBee, send to Telegram, cleanup."""
    user_id = job_data["user_id"]
    chat_id = job_data["chat_id"]
    message_id = job_data["message_id"]
    url = job_data["url"]
    title = job_data["title"]
    duration = normalize_duration(job_data.get("duration"))
    download_type = job_data["download_type"]
    format_string = job_data.get("format_string")
    container = job_data.get("container", "mp4")
    thumbnail = job_data.get("thumbnail")
    log_id = job_data.get("log_id")
    started_at = datetime.utcnow()

    bot = create_bot()
    vidbee = VidBeeClient()
    file_path: str | None = None
    status = "error"
    error_message: str | None = None
    size_mb: float | None = None

    try:
        task = await vidbee.create_download(
            url,
            download_type,
            title=title,
            thumbnail=thumbnail,
            duration=duration,
            format_string=format_string,
            container=container,
        )

        # Store real task id for /cancel
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        await r.set(f"user:{user_id}:task_id", task.id, ex=7200)
        await r.aclose()

        async def on_progress(updated_task):
            await _update_progress_message(
                bot,
                chat_id,
                message_id,
                title,
                updated_task.progress_percent,
                updated_task.speed,
                updated_task.eta,
            )

        completed = await vidbee.wait_completion(task.id, on_progress=on_progress)

        file_path = _resolve_file_path(completed.download_path, completed.saved_file_name)
        if not file_path or not Path(file_path).is_file():
            raise VidBeeError("Файл не найден после загрузки.")

        file_size = Path(file_path).stat().st_size
        size_mb = file_size / (1024 * 1024)
        max_bytes = 2 * 1024 * 1024 * 1024
        if file_size > max_bytes:
            raise VidBeeError(
                f"Файл слишком большой ({file_size / (1024**3):.1f} ГБ). "
                "Попробуйте аудио или более низкое качество."
            )

        await _update_progress_message(bot, chat_id, message_id, title, 100, None, None)
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"📤 Отправляю: <b>{title}</b>...",
        )

        await send_media(
            bot,
            chat_id,
            file_path,
            download_type=download_type,
            title=title,
            duration=duration,
        )

        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"✅ Готово: <b>{title}</b>",
        )
        status = "ok"
        async with get_session() as session:
            if log_id:
                duration_sec = (datetime.utcnow() - started_at).total_seconds()
                await finish_download_log(session, log_id, "ok", size_mb=size_mb, duration_sec=duration_sec)
            unlimited = await has_unlimited_access(user_id)
            premium = await is_premium(session, user_id)
            if not unlimited and not premium:
                await increment_usage(session, user_id)
        return {"status": "ok"}

    except VidBeeError as exc:
        message = humanize_error(exc.category, str(exc))
        error_message = message
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"❌ {message}",
            )
        except TelegramBadRequest:
            await bot.send_message(chat_id, f"❌ {message}")
        return {"status": "error", "message": message}

    except Exception:
        logger.exception("Download job failed for user %s url %s", user_id, url)
        error_message = "Произошла ошибка при загрузке."
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="❌ Произошла ошибка при загрузке.",
            )
        except TelegramBadRequest:
            await bot.send_message(chat_id, "❌ Произошла ошибка при загрузке.")
        return {"status": "error"}

    finally:
        if log_id and status != "ok":
            async with get_session() as session:
                duration_sec = (datetime.utcnow() - started_at).total_seconds()
                await finish_download_log(
                    session,
                    log_id,
                    status,
                    error=error_message,
                    duration_sec=duration_sec,
                )
        if file_path:
            cleanup_file(file_path)
        await clear_active(user_id)
        await vidbee.close()
        await bot.session.close()


async def startup(ctx: dict[str, Any]) -> None:
    from bot.db.session import init_db

    await init_db()
    logger.info("Worker started, max concurrent jobs: %s", settings.max_concurrent_downloads)
    if await sync_cookies_to_vidbee():
        logger.info("Instagram cookies synced in worker")
    else:
        logger.warning("Instagram cookies not configured — see /cookies")


async def shutdown(ctx: dict[str, Any]) -> None:
    logger.info("Worker shutting down")


async def maintenance_cron(ctx: dict[str, Any]) -> None:
    async with get_session() as session:
        from bot.services.analytics import run_maintenance

        await run_maintenance(session)


class WorkerSettings:
    functions = [process_download]
    cron_jobs = [cron(maintenance_cron, hour=3, minute=0)]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = redis_settings()
    max_jobs = settings.max_concurrent_downloads
    job_timeout = 3600
    keep_result = 3600
