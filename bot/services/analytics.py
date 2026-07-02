import logging
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import DailyStat, DownloadLog, Payment, Subscription, User

logger = logging.getLogger(__name__)


async def aggregate_daily_stats(session: AsyncSession, target: date | None = None) -> DailyStat:
    target = target or date.today()
    day_start = datetime.combine(target, datetime.min.time())
    day_end = day_start + timedelta(days=1)

    ok_count = await session.scalar(
        select(func.count())
        .select_from(DownloadLog)
        .where(DownloadLog.created_at >= day_start, DownloadLog.created_at < day_end, DownloadLog.status == "ok")
    )
    fail_count = await session.scalar(
        select(func.count())
        .select_from(DownloadLog)
        .where(
            DownloadLog.created_at >= day_start,
            DownloadLog.created_at < day_end,
            DownloadLog.status == "error",
        )
    )
    active_users = await session.scalar(
        select(func.count(func.distinct(DownloadLog.user_id)))
        .select_from(DownloadLog)
        .where(DownloadLog.created_at >= day_start, DownloadLog.created_at < day_end)
    )
    new_users = await session.scalar(
        select(func.count()).select_from(User).where(User.created_at >= day_start, User.created_at < day_end)
    )
    stars_rev = await session.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .select_from(Payment)
        .where(
            Payment.created_at >= day_start,
            Payment.created_at < day_end,
            Payment.provider == "stars",
            Payment.status == "completed",
        )
    )
    usdt_rev = await session.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0.0))
        .select_from(Payment)
        .where(
            Payment.created_at >= day_start,
            Payment.created_at < day_end,
            Payment.provider == "crypto",
            Payment.status == "completed",
        )
    )
    conversions = await session.scalar(
        select(func.count())
        .select_from(Subscription)
        .where(Subscription.starts_at >= day_start, Subscription.starts_at < day_end, Subscription.source != "manual")
    )

    result = await session.execute(select(DailyStat).where(DailyStat.date == target))
    stat = result.scalar_one_or_none()
    if stat is None:
        stat = DailyStat(date=target)
        session.add(stat)
    stat.downloads_ok = ok_count or 0
    stat.downloads_failed = fail_count or 0
    stat.users_active = active_users or 0
    stat.new_users = new_users or 0
    stat.revenue_stars = int(stars_rev or 0)
    stat.revenue_usdt = float(usdt_rev or 0.0)
    stat.premium_conversions = conversions or 0
    await session.flush()
    return stat


async def run_maintenance(session: AsyncSession) -> dict[str, int]:
    from bot.services.subscription import expire_subscriptions

    expired = await expire_subscriptions(session)
    stat = await aggregate_daily_stats(session)
    logger.info("Maintenance: expired=%s stats=%s", expired, stat.date)
    return {"expired_subscriptions": expired}
