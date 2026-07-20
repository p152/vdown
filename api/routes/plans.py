from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, require_admin
from bot.db.models import Payment, Plan, Subscription

router = APIRouter(prefix="/plans", tags=["plans"], dependencies=[Depends(require_admin)])


class PlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    duration_days: int | None = Field(default=None, gt=0)
    price_stars: int | None = Field(default=None, ge=0)
    price_usdt: float | None = Field(default=None, ge=0)
    is_active: bool | None = None
    sort_order: int | None = None


class PlanCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    duration_days: int = Field(gt=0)
    price_stars: int = Field(default=0, ge=0)
    price_usdt: float = Field(default=0.0, ge=0)
    sort_order: int = 0
    is_active: bool = True


async def _plan_usage(db: AsyncSession, plan_id: int) -> int:
    payments = await db.scalar(
        select(func.count()).select_from(Payment).where(Payment.plan_id == plan_id)
    )
    subscriptions = await db.scalar(
        select(func.count()).select_from(Subscription).where(Subscription.plan_id == plan_id)
    )
    return int(payments or 0) + int(subscriptions or 0)


@router.get("")
async def list_plans(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Plan).order_by(Plan.sort_order, Plan.id))
    plans = result.scalars().all()
    items = []
    for p in plans:
        usage = await _plan_usage(db, p.id)
        items.append(
            {
                "id": p.id,
                "name": p.name,
                "duration_days": p.duration_days,
                "price_stars": p.price_stars,
                "price_usdt": p.price_usdt,
                "is_active": p.is_active,
                "sort_order": p.sort_order,
                "usage_count": usage,
            }
        )
    return items


@router.post("")
async def create_plan(body: PlanCreate, db: AsyncSession = Depends(get_db)):
    plan = Plan(**body.model_dump())
    db.add(plan)
    await db.flush()
    return {"id": plan.id, "ok": True}


@router.patch("/{plan_id}")
async def update_plan(plan_id: int, body: PlanUpdate, db: AsyncSession = Depends(get_db)):
    plan = await db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(404, "Plan not found")
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(400, "No fields to update")
    for key, value in data.items():
        setattr(plan, key, value)
    await db.flush()
    return {"ok": True}


@router.delete("/{plan_id}")
async def delete_plan(plan_id: int, db: AsyncSession = Depends(get_db)):
    plan = await db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(404, "Plan not found")

    usage = await _plan_usage(db, plan_id)
    if usage > 0:
        plan.is_active = False
        await db.flush()
        return {"ok": True, "deactivated": True, "usage_count": usage}

    await db.delete(plan)
    await db.flush()
    return {"ok": True, "deleted": True}
