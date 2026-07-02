from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.db.models import UsageDaily
from bot.services.settings_store import get_free_daily_limit


async def _today() -> date:
    return date.today()


async def get_usage_count(session: AsyncSession, user_id: int, day: date | None = None) -> int:
    target = day or await _today()
    result = await session.execute(
        select(UsageDaily.count).where(UsageDaily.user_id == user_id, UsageDaily.date == target)
    )
    count = result.scalar_one_or_none()
    return count or 0


async def increment_usage(session: AsyncSession, user_id: int) -> int:
    target = await _today()
    result = await session.execute(
        select(UsageDaily).where(UsageDaily.user_id == user_id, UsageDaily.date == target)
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = UsageDaily(user_id=user_id, date=target, count=1)
        session.add(row)
    else:
        row.count += 1
    await session.flush()
    return row.count


async def reset_usage(session: AsyncSession, user_id: int, day: date | None = None) -> None:
    target = day or await _today()
    result = await session.execute(
        select(UsageDaily).where(UsageDaily.user_id == user_id, UsageDaily.date == target)
    )
    row = result.scalar_one_or_none()
    if row:
        row.count = 0
        await session.flush()


async def get_remaining(session: AsyncSession, user_id: int) -> tuple[int, int]:
    limit = await get_free_daily_limit(session)
    used = await get_usage_count(session, user_id)
    return max(0, limit - used), limit


async def can_download_free(session: AsyncSession, user_id: int) -> bool:
    remaining, _ = await get_remaining(session, user_id)
    return remaining > 0


async def count_users_active_since(session: AsyncSession, since: datetime) -> int:
    from bot.db.models import User

    result = await session.execute(select(func.count()).select_from(User).where(User.last_seen >= since))
    return result.scalar_one()


async def count_new_users_since(session: AsyncSession, since: datetime) -> int:
    from bot.db.models import User

    result = await session.execute(select(func.count()).select_from(User).where(User.created_at >= since))
    return result.scalar_one()


def period_start(period: str) -> datetime:
    now = datetime.utcnow()
    if period == "1d":
        return now - timedelta(days=1)
    if period == "7d":
        return now - timedelta(days=7)
    if period == "30d":
        return now - timedelta(days=30)
    return datetime(1970, 1, 1)
