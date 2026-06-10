import json
import logging
from datetime import datetime, timezone

import redis.asyncio as aioredis
from aiogram import Bot
from aiogram.types import User

from bot.config import admin_id_set, settings

logger = logging.getLogger(__name__)

FEEDBACK_KEY = "feedback:list"
FEEDBACK_MAX = 200


async def _redis() -> aioredis.Redis:
    return aioredis.from_url(settings.redis_url, decode_responses=True)


def _user_label(user: User) -> str:
    parts = [user.full_name or "Unknown"]
    if user.username:
        parts.append(f"@{user.username}")
    parts.append(f"id={user.id}")
    return " · ".join(parts)


async def save_feedback(user: User, text: str, *, has_photo: bool = False) -> None:
    entry = {
        "user_id": user.id,
        "username": user.username,
        "name": user.full_name,
        "text": text,
        "has_photo": has_photo,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    r = await _redis()
    try:
        await r.lpush(FEEDBACK_KEY, json.dumps(entry, ensure_ascii=False))
        await r.ltrim(FEEDBACK_KEY, 0, FEEDBACK_MAX - 1)
    finally:
        await r.aclose()


async def list_feedback(limit: int = 10) -> list[dict]:
    r = await _redis()
    try:
        raw_items = await r.lrange(FEEDBACK_KEY, 0, limit - 1)
    finally:
        await r.aclose()

    items: list[dict] = []
    for raw in raw_items:
        try:
            items.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return items


async def notify_admins(
    bot: Bot,
    user: User,
    text: str,
    *,
    photo_file_id: str | None = None,
) -> None:
    header = f"🐛 <b>Обратная связь</b>\n👤 {_user_label(user)}\n\n{text}"
    targets: list[int] = []

    if settings.feedback_chat_id:
        targets.append(settings.feedback_chat_id)
    else:
        targets.extend(admin_id_set())

    if not targets:
        logger.warning("Feedback received but no FEEDBACK_CHAT_ID or ADMIN_IDS configured")
        return

    for chat_id in targets:
        try:
            if photo_file_id:
                await bot.send_photo(
                    chat_id,
                    photo=photo_file_id,
                    caption=header,
                )
            else:
                await bot.send_message(chat_id, header)
        except Exception:
            logger.exception("Failed to send feedback to chat %s", chat_id)
