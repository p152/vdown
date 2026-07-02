from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Payment, Plan, Subscription


async def is_premium(session: AsyncSession, user_id: int) -> bool:
    now = datetime.utcnow()
    result = await session.execute(
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.status == "active",
            Subscription.expires_at > now,
        )
        .order_by(Subscription.expires_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def get_active_subscription(session: AsyncSession, user_id: int) -> Subscription | None:
    now = datetime.utcnow()
    result = await session.execute(
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.status == "active",
            Subscription.expires_at > now,
        )
        .order_by(Subscription.expires_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def activate_subscription(
    session: AsyncSession,
    user_id: int,
    plan: Plan,
    source: str,
    payment: Payment | None = None,
) -> Subscription:
    now = datetime.utcnow()
    existing = await get_active_subscription(session, user_id)
    if existing:
        base = existing.expires_at if existing.expires_at > now else now
    else:
        base = now
    expires_at = base + timedelta(days=plan.duration_days)
    sub = Subscription(
        user_id=user_id,
        plan_id=plan.id,
        status="active",
        starts_at=now,
        expires_at=expires_at,
        source=source,
    )
    session.add(sub)
    await session.flush()
    if payment:
        payment.status = "completed"
    return sub


async def revoke_premium(session: AsyncSession, user_id: int) -> int:
    now = datetime.utcnow()
    result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status == "active",
            Subscription.expires_at > now,
        )
    )
    subs = result.scalars().all()
    for sub in subs:
        sub.status = "revoked"
        sub.expires_at = now
    await session.flush()
    return len(subs)


async def grant_premium(session: AsyncSession, user_id: int, plan: Plan) -> Subscription:
    return await activate_subscription(session, user_id, plan, source="manual")


async def expire_subscriptions(session: AsyncSession) -> int:
    now = datetime.utcnow()
    result = await session.execute(
        select(Subscription).where(
            Subscription.status == "active",
            Subscription.expires_at <= now,
        )
    )
    subs = result.scalars().all()
    for sub in subs:
        sub.status = "expired"
    await session.flush()
    return len(subs)


async def get_plan(session: AsyncSession, plan_id: int) -> Plan | None:
    result = await session.execute(select(Plan).where(Plan.id == plan_id, Plan.is_active.is_(True)))
    return result.scalar_one_or_none()


async def list_plans(session: AsyncSession, active_only: bool = True) -> list[Plan]:
    query = select(Plan).order_by(Plan.sort_order, Plan.id)
    if active_only:
        query = query.where(Plan.is_active.is_(True))
    result = await session.execute(query)
    return list(result.scalars().all())


async def record_payment(
    session: AsyncSession,
    user_id: int,
    plan: Plan,
    provider: str,
    amount: float,
    currency: str,
    external_id: str,
) -> Payment | None:
    existing = await session.execute(select(Payment).where(Payment.external_id == external_id))
    if existing.scalar_one_or_none():
        return None
    payment = Payment(
        user_id=user_id,
        plan_id=plan.id,
        provider=provider,
        amount=amount,
        currency=currency,
        external_id=external_id,
        status="completed",
    )
    session.add(payment)
    await session.flush()
    return payment
