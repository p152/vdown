from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, require_admin
from bot.services.settings_store import get_free_daily_limit, get_setting, set_setting

router = APIRouter(prefix="/settings", tags=["settings"], dependencies=[Depends(require_admin)])


class SettingsUpdate(BaseModel):
    free_daily_limit: int | None = None
    maintenance_mode: str | None = None


@router.get("")
async def get_settings(db: AsyncSession = Depends(get_db)):
    return {
        "free_daily_limit": await get_free_daily_limit(db),
        "maintenance_mode": await get_setting(db, "maintenance_mode", "false"),
    }


@router.patch("")
async def update_settings(body: SettingsUpdate, db: AsyncSession = Depends(get_db)):
    if body.free_daily_limit is not None:
        await set_setting(db, "free_daily_limit", str(body.free_daily_limit))
    if body.maintenance_mode is not None:
        await set_setting(db, "maintenance_mode", body.maintenance_mode)
    return {"ok": True}
