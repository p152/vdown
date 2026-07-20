import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import require_admin
from bot.services.cookies_manager import (
    delete_platform_cookies,
    get_vidbee_settings,
    list_platform_statuses,
    save_platform_cookies,
    set_vidbee_proxy,
    sync_cookies_to_vidbee,
)
from bot.services.platform_catalog import get_platform

router = APIRouter(prefix="/services", tags=["services"], dependencies=[Depends(require_admin)])
logger = logging.getLogger(__name__)


class CookiesUploadBody(BaseModel):
    content: str = Field(min_length=10, max_length=500_000)


class ProxyUpdateBody(BaseModel):
    proxy: str = ""


@router.get("")
async def list_services():
    platforms = list_platform_statuses()
    vidbee = await get_vidbee_settings()
    return {"platforms": platforms, "vidbee": vidbee}


@router.post("/{platform_id}/cookies")
async def upload_platform_cookies(platform_id: str, body: CookiesUploadBody):
    if get_platform(platform_id) is None:
        raise HTTPException(404, "Platform not found")
    try:
        return await save_platform_cookies(platform_id, body.content)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/{platform_id}/cookies")
async def remove_platform_cookies(platform_id: str):
    if get_platform(platform_id) is None:
        raise HTTPException(404, "Platform not found")
    try:
        return await delete_platform_cookies(platform_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/sync")
async def sync_services():
    ok = await sync_cookies_to_vidbee()
    return {"ok": ok}


@router.patch("/vidbee/proxy")
async def update_vidbee_proxy(body: ProxyUpdateBody):
    return await set_vidbee_proxy(body.proxy)
