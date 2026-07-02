from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.db.models import AppSetting, Plan


async def get_setting(session: AsyncSession, key: str, default: str = "") -> str:
    result = await session.execute(select(AppSetting).where(AppSetting.key == key))
    row = result.scalar_one_or_none()
    return row.value if row else default


async def set_setting(session: AsyncSession, key: str, value: str) -> None:
    result = await session.execute(select(AppSetting).where(AppSetting.key == key))
    row = result.scalar_one_or_none()
    if row is None:
        session.add(AppSetting(key=key, value=value))
    else:
        row.value = value
    await session.flush()


async def get_free_daily_limit(session: AsyncSession) -> int:
    value = await get_setting(session, "free_daily_limit", str(settings.free_daily_limit))
    try:
        return max(1, int(value))
    except ValueError:
        return settings.free_daily_limit


async def seed_defaults(session: AsyncSession) -> None:
    result = await session.execute(select(Plan).limit(1))
    if result.scalar_one_or_none() is None:
        session.add_all(
            [
                Plan(name="7 дней", duration_days=7, price_stars=50, price_usdt=1.0, sort_order=1),
                Plan(name="30 дней", duration_days=30, price_stars=150, price_usdt=3.0, sort_order=2),
                Plan(name="365 дней", duration_days=365, price_stars=1200, price_usdt=25.0, sort_order=3),
            ]
        )
    limit = await get_setting(session, "free_daily_limit")
    if not limit:
        await set_setting(session, "free_daily_limit", str(settings.free_daily_limit))
    await session.flush()
