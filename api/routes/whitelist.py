from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.deps import require_admin
from bot.services.access_store import (
    add_group,
    add_user,
    is_whitelist_active,
    list_groups,
    list_users,
    remove_group,
    remove_user,
)

router = APIRouter(prefix="/whitelist", tags=["whitelist"], dependencies=[Depends(require_admin)])


class IdRequest(BaseModel):
    id: int


@router.get("")
async def whitelist_status():
    return {
        "active": await is_whitelist_active(),
        "users": await list_users(),
        "groups": await list_groups(),
    }


@router.post("/users")
async def whitelist_add_user(body: IdRequest):
    added = await add_user(body.id)
    return {"ok": True, "added": added}


@router.delete("/users/{user_id}")
async def whitelist_remove_user(user_id: int):
    removed = await remove_user(user_id)
    return {"ok": True, "removed": removed}


@router.post("/groups")
async def whitelist_add_group(body: IdRequest):
    added = await add_group(body.id)
    return {"ok": True, "added": added}


@router.delete("/groups/{group_id}")
async def whitelist_remove_group(group_id: int):
    removed = await remove_group(group_id)
    return {"ok": True, "removed": removed}
