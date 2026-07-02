from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, require_admin
from bot.db.models import Payment, Plan, User

router = APIRouter(prefix="/payments", tags=["payments"], dependencies=[Depends(require_admin)])


@router.get("")
async def list_payments(
    provider: str | None = None,
    offset: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    query = select(Payment, Plan.name, User.username).join(Plan).join(User).order_by(Payment.created_at.desc())
    if provider:
        query = query.where(Payment.provider == provider)
    result = await db.execute(query.offset(offset).limit(limit))
    return [
        {
            "id": p.id,
            "user_id": p.user_id,
            "username": username,
            "plan": plan_name,
            "provider": p.provider,
            "amount": p.amount,
            "currency": p.currency,
            "status": p.status,
            "created_at": p.created_at.isoformat(),
        }
        for p, plan_name, username in result.all()
    ]
