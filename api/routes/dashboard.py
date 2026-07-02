from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, require_admin
from bot.db.models import DownloadLog, Payment, Subscription, User
from bot.services.usage import period_start

router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(require_admin)])


@router.get("/overview")
async def overview(period: str = "7d", db: AsyncSession = Depends(get_db)):
    since = period_start(period)
    now = datetime.utcnow()

    total_users = await db.scalar(select(func.count()).select_from(User))
    new_users = await db.scalar(select(func.count()).select_from(User).where(User.created_at >= since))
    active_users = await db.scalar(select(func.count()).select_from(User).where(User.last_seen >= since))

    downloads_ok = await db.scalar(
        select(func.count())
        .select_from(DownloadLog)
        .where(DownloadLog.created_at >= since, DownloadLog.status == "ok")
    )
    downloads_failed = await db.scalar(
        select(func.count())
        .select_from(DownloadLog)
        .where(DownloadLog.created_at >= since, DownloadLog.status == "error")
    )

    premium_active = await db.scalar(
        select(func.count(func.distinct(Subscription.user_id)))
        .select_from(Subscription)
        .where(Subscription.status == "active", Subscription.expires_at > now)
    )
    premium_new = await db.scalar(
        select(func.count())
        .select_from(Subscription)
        .where(Subscription.starts_at >= since, Subscription.source != "manual")
    )

    stars_rev = await db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .select_from(Payment)
        .where(Payment.created_at >= since, Payment.provider == "stars", Payment.status == "completed")
    )
    usdt_rev = await db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0.0))
        .select_from(Payment)
        .where(Payment.created_at >= since, Payment.provider == "crypto", Payment.status == "completed")
    )

    return {
        "period": period,
        "users_total": total_users or 0,
        "users_new": new_users or 0,
        "users_active": active_users or 0,
        "downloads_ok": downloads_ok or 0,
        "downloads_failed": downloads_failed or 0,
        "premium_active": premium_active or 0,
        "premium_new": premium_new or 0,
        "revenue_stars": int(stars_rev or 0),
        "revenue_usdt": float(usdt_rev or 0.0),
    }
