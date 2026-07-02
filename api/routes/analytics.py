import csv
import io
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, require_admin
from bot.db.models import DailyStat, DownloadLog, Payment, Plan, Subscription, User
from bot.services.usage import period_start

router = APIRouter(tags=["analytics"], dependencies=[Depends(require_admin)])


def _days_for_period(period: str) -> int:
    return {"1d": 1, "7d": 7, "30d": 30}.get(period, 7)


@router.get("/analytics/charts/downloads")
async def chart_downloads(period: str = "30d", db: AsyncSession = Depends(get_db)):
    days = _days_for_period(period)
    start = date.today() - timedelta(days=days - 1)
    result = await db.execute(select(DailyStat).where(DailyStat.date >= start).order_by(DailyStat.date))
    stats = result.scalars().all()
    if not stats:
        labels = [(start + timedelta(days=i)).isoformat() for i in range(days)]
        return {"labels": labels, "ok": [0] * days, "failed": [0] * days}
    return {
        "labels": [s.date.isoformat() for s in stats],
        "ok": [s.downloads_ok for s in stats],
        "failed": [s.downloads_failed for s in stats],
    }


@router.get("/analytics/charts/revenue")
async def chart_revenue(period: str = "30d", db: AsyncSession = Depends(get_db)):
    days = _days_for_period(period)
    start = date.today() - timedelta(days=days - 1)
    result = await db.execute(select(DailyStat).where(DailyStat.date >= start).order_by(DailyStat.date))
    stats = result.scalars().all()
    return {
        "labels": [s.date.isoformat() for s in stats],
        "stars": [s.revenue_stars for s in stats],
        "usdt": [s.revenue_usdt for s in stats],
    }


@router.get("/analytics/charts/users")
async def chart_users(period: str = "30d", db: AsyncSession = Depends(get_db)):
    days = _days_for_period(period)
    start = date.today() - timedelta(days=days - 1)
    result = await db.execute(select(DailyStat).where(DailyStat.date >= start).order_by(DailyStat.date))
    stats = result.scalars().all()
    return {
        "labels": [s.date.isoformat() for s in stats],
        "new_users": [s.new_users for s in stats],
        "active": [s.users_active for s in stats],
    }


@router.get("/analytics/downloads/domains")
async def top_domains(period: str = "30d", limit: int = 10, db: AsyncSession = Depends(get_db)):
    since = period_start(period)
    result = await db.execute(
        select(DownloadLog.domain, func.count())
        .where(DownloadLog.created_at >= since, DownloadLog.status == "ok")
        .group_by(DownloadLog.domain)
        .order_by(func.count().desc())
        .limit(limit)
    )
    rows = result.all()
    return {"labels": [r[0] for r in rows], "values": [r[1] for r in rows]}


@router.get("/analytics/downloads/formats")
async def format_stats(period: str = "30d", db: AsyncSession = Depends(get_db)):
    since = period_start(period)
    result = await db.execute(
        select(DownloadLog.format_choice, func.count())
        .where(DownloadLog.created_at >= since, DownloadLog.status == "ok")
        .group_by(DownloadLog.format_choice)
        .order_by(func.count().desc())
    )
    rows = result.all()
    return {"labels": [r[0] or "auto" for r in rows], "values": [r[1] for r in rows]}


@router.get("/analytics/downloads/errors")
async def top_errors(period: str = "30d", limit: int = 10, db: AsyncSession = Depends(get_db)):
    since = period_start(period)
    result = await db.execute(
        select(DownloadLog.error, func.count())
        .where(DownloadLog.created_at >= since, DownloadLog.status == "error", DownloadLog.error.isnot(None))
        .group_by(DownloadLog.error)
        .order_by(func.count().desc())
        .limit(limit)
    )
    rows = result.all()
    return {"labels": [(r[0] or "")[:80] for r in rows], "values": [r[1] for r in rows]}


@router.get("/analytics/users/segments")
async def user_segments(db: AsyncSession = Depends(get_db)):
    now = datetime.utcnow()
    total = await db.scalar(select(func.count()).select_from(User)) or 0
    premium = await db.scalar(
        select(func.count(func.distinct(Subscription.user_id)))
        .select_from(Subscription)
        .where(Subscription.status == "active", Subscription.expires_at > now)
    ) or 0
    active = await db.scalar(
        select(func.count()).select_from(User).where(User.last_seen >= now - timedelta(days=7))
    ) or 0
    dormant = await db.scalar(
        select(func.count()).select_from(User).where(User.last_seen < now - timedelta(days=30))
    ) or 0
    return {
        "total": total,
        "premium": premium,
        "free": max(0, total - premium),
        "active_7d": active,
        "dormant_30d": dormant,
    }


@router.get("/analytics/users/top")
async def top_users(period: str = "30d", limit: int = 20, db: AsyncSession = Depends(get_db)):
    since = period_start(period)
    result = await db.execute(
        select(DownloadLog.user_id, User.username, User.first_name, func.count())
        .join(User, User.telegram_id == DownloadLog.user_id)
        .where(DownloadLog.created_at >= since, DownloadLog.status == "ok")
        .group_by(DownloadLog.user_id, User.username, User.first_name)
        .order_by(func.count().desc())
        .limit(limit)
    )
    return [
        {"user_id": r[0], "username": r[1], "first_name": r[2], "downloads": r[3]}
        for r in result.all()
    ]


@router.get("/analytics/revenue/breakdown")
async def revenue_breakdown(period: str = "30d", db: AsyncSession = Depends(get_db)):
    since = period_start(period)
    result = await db.execute(
        select(Plan.name, Payment.provider, func.sum(Payment.amount), func.count())
        .join(Plan, Plan.id == Payment.plan_id)
        .where(Payment.created_at >= since, Payment.status == "completed")
        .group_by(Plan.name, Payment.provider)
    )
    return [
        {"plan": r[0], "provider": r[1], "amount": float(r[2] or 0), "count": r[3]}
        for r in result.all()
    ]


@router.get("/analytics/system")
async def system_stats(db: AsyncSession = Depends(get_db)):
    from bot.config import settings
    import redis.asyncio as aioredis

    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        queue_len = await r.llen("arq:queue")
    finally:
        await r.aclose()

    since = datetime.utcnow() - timedelta(days=7)
    avg_time = await db.scalar(
        select(func.avg(DownloadLog.duration_sec))
        .where(DownloadLog.status == "ok", DownloadLog.duration_sec.isnot(None), DownloadLog.created_at >= since)
    )
    failed = await db.scalar(
        select(func.count()).select_from(DownloadLog).where(DownloadLog.status == "error", DownloadLog.created_at >= since)
    )
    return {
        "queue_length": queue_len,
        "avg_download_sec": round(float(avg_time or 0), 1),
        "failed_7d": failed or 0,
        "max_concurrent": settings.max_concurrent_downloads,
    }


@router.get("/reports/users")
async def report_users(
    period: str = "30d",
    offset: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    since = period_start(period)
    result = await db.execute(
        select(User).order_by(User.last_seen.desc()).offset(offset).limit(limit)
    )
    users = result.scalars().all()
    now = datetime.utcnow()
    rows = []
    for user in users:
        downloads = await db.scalar(
            select(func.count())
            .select_from(DownloadLog)
            .where(DownloadLog.user_id == user.telegram_id, DownloadLog.created_at >= since, DownloadLog.status == "ok")
        )
        sub = await db.scalar(
            select(Subscription)
            .where(Subscription.user_id == user.telegram_id, Subscription.status == "active", Subscription.expires_at > now)
            .order_by(Subscription.expires_at.desc())
            .limit(1)
        )
        spent = await db.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0))
            .where(Payment.user_id == user.telegram_id, Payment.status == "completed")
        )
        rows.append(
            {
                "telegram_id": user.telegram_id,
                "username": user.username,
                "first_name": user.first_name,
                "created_at": user.created_at.isoformat(),
                "last_seen": user.last_seen.isoformat(),
                "downloads": downloads or 0,
                "premium_until": sub.expires_at.isoformat() if sub else None,
                "spent": float(spent or 0),
            }
        )
    total = await db.scalar(select(func.count()).select_from(User))
    return {"total": total or 0, "items": rows}


@router.get("/reports/users/export")
async def export_users(period: str = "30d", db: AsyncSession = Depends(get_db)):
    data = await report_users(period=period, offset=0, limit=10000, db=db)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["telegram_id", "username", "first_name", "created_at", "last_seen", "downloads", "premium_until", "spent"])
    for row in data["items"]:
        writer.writerow(
            [
                row["telegram_id"],
                row["username"] or "",
                row["first_name"] or "",
                row["created_at"],
                row["last_seen"],
                row["downloads"],
                row["premium_until"] or "",
                row["spent"],
            ]
        )
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=users_report.csv"},
    )


@router.get("/users/{user_id}")
async def user_detail(user_id: int, db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if not user:
        return {"error": "not found"}
    now = datetime.utcnow()
    subs = await db.execute(
        select(Subscription, Plan.name)
        .join(Plan, Plan.id == Subscription.plan_id)
        .where(Subscription.user_id == user_id)
        .order_by(Subscription.starts_at.desc())
        .limit(20)
    )
    payments = await db.execute(
        select(Payment).where(Payment.user_id == user_id).order_by(Payment.created_at.desc()).limit(20)
    )
    logs = await db.execute(
        select(DownloadLog).where(DownloadLog.user_id == user_id).order_by(DownloadLog.created_at.desc()).limit(50)
    )
    return {
        "user": {
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "created_at": user.created_at.isoformat(),
            "last_seen": user.last_seen.isoformat(),
        },
        "subscriptions": [
            {
                "plan": name,
                "status": s.status,
                "starts_at": s.starts_at.isoformat(),
                "expires_at": s.expires_at.isoformat(),
                "source": s.source,
            }
            for s, name in subs.all()
        ],
        "payments": [
            {
                "provider": p.provider,
                "amount": p.amount,
                "currency": p.currency,
                "status": p.status,
                "created_at": p.created_at.isoformat(),
            }
            for p in payments.scalars().all()
        ],
        "downloads": [
            {
                "url": l.url,
                "domain": l.domain,
                "status": l.status,
                "size_mb": l.size_mb,
                "created_at": l.created_at.isoformat(),
            }
            for l in logs.scalars().all()
        ],
    }
