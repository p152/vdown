from bot.access import is_admin
from bot.services.access_store import is_user_allowed, is_whitelist_active


async def has_unlimited_access(user_id: int) -> bool:
    """Unlimited downloads: admins and individually whitelisted users only.

    Whitelisted groups grant bot access in chat (see access_store.is_chat_allowed)
    but do not bypass freemium / Premium limits for members.
    """
    if is_admin(user_id):
        return True
    if not await is_whitelist_active():
        return False
    return await is_user_allowed(user_id)
