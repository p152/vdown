from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import PasswordAuth, TelegramAuthData, create_access_token, verify_password, verify_telegram_login
from bot.config import admin_id_set
from api.deps import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/telegram")
async def auth_telegram(data: TelegramAuthData, response: Response, db: AsyncSession = Depends(get_db)):
    del db
    if not verify_telegram_login(data):
        return {"ok": False, "error": "Invalid Telegram auth or not admin"}
    token = create_access_token(data.id)
    response.set_cookie("access_token", token, httponly=True, max_age=86400, samesite="lax")
    return {"ok": True, "token": token, "admin_id": data.id}


@router.post("/password")
async def auth_password(data: PasswordAuth, response: Response):
    if not verify_password(data.password):
        return {"ok": False, "error": "Invalid password"}
    admins = admin_id_set()
    admin_id = next(iter(admins), 0)
    token = create_access_token(admin_id)
    response.set_cookie("access_token", token, httponly=True, max_age=86400, samesite="lax")
    return {"ok": True, "token": token}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    return {"ok": True}
