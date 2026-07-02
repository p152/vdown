from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.auth import decode_token
from bot.config import admin_id_set, settings

security = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator:
    from sqlalchemy.ext.asyncio import AsyncSession

    from bot.db.session import session_factory

    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def require_admin(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> int:
    token = None
    if credentials:
        token = credentials.credentials
    elif "access_token" in request.cookies:
        token = request.cookies["access_token"]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    admin_id = decode_token(token)
    admins = admin_id_set()
    if admin_id is None:
        raise HTTPException(status_code=403, detail="Forbidden")
    if admins:
        if admin_id not in admins:
            raise HTTPException(status_code=403, detail="Forbidden")
    elif not settings.admin_web_password:
        raise HTTPException(status_code=403, detail="ADMIN_IDS or ADMIN_WEB_PASSWORD required")
    return admin_id
