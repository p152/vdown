from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import DownloadLog
from bot.utils.urls import extract_domain


async def start_download_log(
    session: AsyncSession,
    user_id: int,
    url: str,
    format_choice: str | None = None,
) -> DownloadLog:
    log = DownloadLog(
        user_id=user_id,
        url=url,
        domain=extract_domain(url),
        format_choice=format_choice,
        status="started",
        created_at=datetime.utcnow(),
    )
    session.add(log)
    await session.flush()
    return log


async def finish_download_log(
    session: AsyncSession,
    log_id: int,
    status: str,
    size_mb: float | None = None,
    error: str | None = None,
    duration_sec: float | None = None,
) -> None:
    log = await session.get(DownloadLog, log_id)
    if not log:
        return
    log.status = status
    log.size_mb = size_mb
    log.error = error
    log.duration_sec = duration_sec
    log.finished_at = datetime.utcnow()
    await session.flush()
