import json
import logging
from dataclasses import asdict, dataclass
from typing import Any

import redis.asyncio as redis
from arq import create_pool
from arq.connections import RedisSettings

from bot.config import settings
from bot.utils.formats import normalize_duration

logger = logging.getLogger(__name__)

PENDING_KEY = "pending:{user_id}"
ACTIVE_KEY = "user:{user_id}:active"
ACTIVE_TASK_KEY = "user:{user_id}:task_id"


@dataclass
class PendingDownload:
    url: str
    title: str
    duration: int | None
    thumbnail: str | None
    uploader: str | None
    chat_id: int
    message_id: int


@dataclass
class DownloadJob:
    user_id: int
    chat_id: int
    message_id: int
    url: str
    title: str
    duration: int | None
    thumbnail: str | None
    format_choice: str
    download_type: str
    format_string: str | None
    container: str
    log_id: int | None = None


def redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(settings.redis_url)


async def get_redis() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


async def save_pending(user_id: int, pending: PendingDownload) -> None:
    r = await get_redis()
    try:
        await r.set(PENDING_KEY.format(user_id=user_id), json.dumps(asdict(pending)), ex=3600)
    finally:
        await r.aclose()


async def load_pending(user_id: int) -> PendingDownload | None:
    r = await get_redis()
    try:
        raw = await r.get(PENDING_KEY.format(user_id=user_id))
        if not raw:
            return None
        data = json.loads(raw)
        data["duration"] = normalize_duration(data.get("duration"))
        return PendingDownload(**data)
    finally:
        await r.aclose()


async def clear_pending(user_id: int) -> None:
    r = await get_redis()
    try:
        await r.delete(PENDING_KEY.format(user_id=user_id))
    finally:
        await r.aclose()


async def set_active(user_id: int, task_id: str) -> bool:
    """Return False if user already has active download."""
    r = await get_redis()
    try:
        key = ACTIVE_KEY.format(user_id=user_id)
        was_set = await r.set(key, task_id, nx=True, ex=7200)
        if was_set:
            await r.set(ACTIVE_TASK_KEY.format(user_id=user_id), task_id, ex=7200)
        return bool(was_set)
    finally:
        await r.aclose()


async def get_active_task_id(user_id: int) -> str | None:
    r = await get_redis()
    try:
        return await r.get(ACTIVE_TASK_KEY.format(user_id=user_id))
    finally:
        await r.aclose()


async def clear_active(user_id: int) -> None:
    r = await get_redis()
    try:
        await r.delete(
            ACTIVE_KEY.format(user_id=user_id),
            ACTIVE_TASK_KEY.format(user_id=user_id),
        )
    finally:
        await r.aclose()


async def enqueue_download(job: DownloadJob) -> str | None:
    pool = await create_pool(redis_settings())
    try:
        arq_job = await pool.enqueue_job("process_download", job.__dict__)
        return arq_job.job_id if arq_job else None
    finally:
        await pool.aclose()
