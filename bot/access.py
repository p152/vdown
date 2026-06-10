from bot.config import admin_id_set


def is_admin(user_id: int) -> bool:
    admins = admin_id_set()
    return bool(admins) and user_id in admins


def can_upload_cookies(user_id: int) -> bool:
    admins = admin_id_set()
    return not admins or user_id in admins
