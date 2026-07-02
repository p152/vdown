from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.access_check import has_unlimited_access
from bot.services.subscription import get_active_subscription, is_premium
from bot.services.usage import get_remaining


@dataclass
class AccessStatus:
    allowed: bool
    reason: str
    remaining: int = 0
    limit: int = 0
    premium_until: str | None = None


async def check_download_access(session: AsyncSession, user_id: int, chat_id: int) -> AccessStatus:
    if await has_unlimited_access(user_id, chat_id):
        return AccessStatus(allowed=True, reason="unlimited")

    if await is_premium(session, user_id):
        sub = await get_active_subscription(session, user_id)
        until = sub.expires_at.strftime("%d.%m.%Y") if sub else None
        return AccessStatus(allowed=True, reason="premium", premium_until=until)

    remaining, limit = await get_remaining(session, user_id)
    if remaining > 0:
        return AccessStatus(allowed=True, reason="free", remaining=remaining, limit=limit)

    return AccessStatus(allowed=False, reason="limit", remaining=0, limit=limit)
