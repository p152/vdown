from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, require_admin
from bot.db.models import Plan

router = APIRouter(prefix="/plans", tags=["plans"], dependencies=[Depends(require_admin)])


class PlanUpdate(BaseModel):
    name: str | None = None
    duration_days: int | None = None
    price_stars: int | None = None
    price_usdt: float | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class PlanCreate(BaseModel):
    name: str
    duration_days: int
    price_stars: int = 0
    price_usdt: float = 0.0
    sort_order: int = 0


@router.get("")
async def list_plans(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Plan).order_by(Plan.sort_order, Plan.id))
    plans = result.scalars().all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "duration_days": p.duration_days,
            "price_stars": p.price_stars,
            "price_usdt": p.price_usdt,
            "is_active": p.is_active,
            "sort_order": p.sort_order,
        }
        for p in plans
    ]


@router.post("")
async def create_plan(body: PlanCreate, db: AsyncSession = Depends(get_db)):
    plan = Plan(**body.model_dump())
    db.add(plan)
    await db.flush()
    return {"id": plan.id}


@router.patch("/{plan_id}")
async def update_plan(plan_id: int, body: PlanUpdate, db: AsyncSession = Depends(get_db)):
    plan = await db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(404, "Plan not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(plan, key, value)
    await db.flush()
    return {"ok": True}
