from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, require_admin
from bot.db.models import User
from bot.services.subscription import get_plan, grant_premium, revoke_premium
from bot.services.usage import reset_usage

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(require_admin)])


class GrantPremiumRequest(BaseModel):
    plan_id: int


@router.get("")
async def list_users(q: str = "", offset: int = 0, limit: int = 50, db: AsyncSession = Depends(get_db)):
    query = select(User).order_by(User.last_seen.desc())
    if q.isdigit():
        query = query.where(User.telegram_id == int(q))
    elif q:
        query = query.where(User.username.ilike(f"%{q}%"))
    result = await db.execute(query.offset(offset).limit(limit))
    users = result.scalars().all()
    return [
        {
            "telegram_id": u.telegram_id,
            "username": u.username,
            "first_name": u.first_name,
            "last_seen": u.last_seen.isoformat(),
        }
        for u in users
    ]


@router.post("/{user_id}/grant-premium")
async def grant_user_premium(user_id: int, body: GrantPremiumRequest, db: AsyncSession = Depends(get_db)):
    plan = await get_plan(db, body.plan_id)
    if not plan:
        raise HTTPException(404, "Plan not found")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    sub = await grant_premium(db, user_id, plan)
    return {"ok": True, "expires_at": sub.expires_at.isoformat()}


@router.post("/{user_id}/revoke-premium")
async def revoke_user_premium(user_id: int, db: AsyncSession = Depends(get_db)):
    count = await revoke_premium(db, user_id)
    return {"ok": True, "revoked": count}


@router.post("/{user_id}/reset-limit")
async def reset_user_limit(user_id: int, db: AsyncSession = Depends(get_db)):
    await reset_usage(db, user_id)
    return {"ok": True}
