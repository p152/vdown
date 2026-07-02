import logging

from bot.access import is_admin
from bot.services.access_store import is_user_allowed, is_whitelist_active

logger = logging.getLogger(__name__)


async def has_unlimited_access(user_id: int, chat_id: int) -> bool:
    if is_admin(user_id):
        return True
    if not await is_whitelist_active():
        return False
    if await is_user_allowed(user_id):
        return True
    from bot.services.access_store import is_chat_allowed

    return await is_chat_allowed(chat_id, user_id)
