import logging

import redis.asyncio as aioredis

from bot.config import settings

logger = logging.getLogger(__name__)

USERS_KEY = "access:users"
GROUPS_KEY = "access:groups"


async def _redis() -> aioredis.Redis:
    return aioredis.from_url(settings.redis_url, decode_responses=True)


async def is_whitelist_active() -> bool:
    r = await _redis()
    try:
        users_count = await r.scard(USERS_KEY)
        groups_count = await r.scard(GROUPS_KEY)
        return users_count > 0 or groups_count > 0
    finally:
        await r.aclose()


async def is_user_allowed(user_id: int) -> bool:
    if not await is_whitelist_active():
        return True
    r = await _redis()
    try:
        return await r.sismember(USERS_KEY, str(user_id))
    finally:
        await r.aclose()


async def is_chat_allowed(chat_id: int, user_id: int) -> bool:
    if not await is_whitelist_active():
        return True
    if await is_user_allowed(user_id):
        return True
    r = await _redis()
    try:
        return await r.sismember(GROUPS_KEY, str(chat_id))
    finally:
        await r.aclose()


async def add_user(user_id: int) -> bool:
    r = await _redis()
    try:
        added = await r.sadd(USERS_KEY, str(user_id))
        logger.info("Access: added user %s", user_id)
        return bool(added)
    finally:
        await r.aclose()


async def remove_user(user_id: int) -> bool:
    r = await _redis()
    try:
        removed = await r.srem(USERS_KEY, str(user_id))
        logger.info("Access: removed user %s", user_id)
        return bool(removed)
    finally:
        await r.aclose()


async def list_users() -> list[int]:
    r = await _redis()
    try:
        members = await r.smembers(USERS_KEY)
        return sorted(int(item) for item in members if item.lstrip("-").isdigit())
    finally:
        await r.aclose()


async def add_group(chat_id: int) -> bool:
    r = await _redis()
    try:
        added = await r.sadd(GROUPS_KEY, str(chat_id))
        logger.info("Access: added group %s", chat_id)
        return bool(added)
    finally:
        await r.aclose()


async def remove_group(chat_id: int) -> bool:
    r = await _redis()
    try:
        removed = await r.srem(GROUPS_KEY, str(chat_id))
        logger.info("Access: removed group %s", chat_id)
        return bool(removed)
    finally:
        await r.aclose()


async def list_groups() -> list[int]:
    r = await _redis()
    try:
        members = await r.smembers(GROUPS_KEY)
        return sorted(int(item) for item in members if item.lstrip("-").isdigit())
    finally:
        await r.aclose()
