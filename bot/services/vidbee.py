import json
import logging
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

import aiohttp

from bot.config import settings
from bot.utils.formats import normalize_duration

logger = logging.getLogger(__name__)

ERROR_MESSAGES: dict[str, str] = {
    "geo-blocked": "Видео недоступно в вашем регионе.",
    "auth-required": "Требуется авторизация (возрастное ограничение или приватное видео).",
    "not-found": "Видео не найдено или ссылка недействительна.",
    "disk-full": "Недостаточно места на сервере.",
    "http-429": "Слишком много запросов. Попробуйте позже.",
    "network-transient": "Сетевая ошибка. Попробуйте ещё раз.",
    "cancelled-by-user": "Загрузка отменена.",
}


@dataclass
class VideoInfo:
    id: str
    title: str
    thumbnail: str | None
    duration: int | None
    uploader: str | None
    formats: list[dict[str, Any]]
    webpage_url: str | None = None


@dataclass
class DownloadTask:
    id: str
    url: str
    title: str | None
    status: str
    download_path: str | None = None
    saved_file_name: str | None = None
    error: str | None = None
    error_category: str | None = None
    progress_percent: float = 0.0
    speed: str | None = None
    eta: str | None = None


class VidBeeError(Exception):
    def __init__(self, message: str, category: str | None = None):
        super().__init__(message)
        self.category = category


class VidBeeClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.vidbee_api_url).rstrip("/")
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=600, connect=30)
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    def _runtime_settings(self) -> dict[str, Any] | None:
        from bot.services.cookies import get_cookies_path

        runtime: dict[str, Any] = {}
        if settings.vidbee_proxy:
            runtime["proxy"] = settings.vidbee_proxy
        cookies_path = get_cookies_path()
        if cookies_path:
            runtime["cookiesPath"] = cookies_path
        return runtime or None

    async def _runtime_settings_async(self) -> dict[str, Any] | None:
        from bot.services.cookies_manager import ensure_cookies_synced

        runtime: dict[str, Any] = {}
        if settings.vidbee_proxy:
            runtime["proxy"] = settings.vidbee_proxy
        cookies_path = await ensure_cookies_synced()
        if cookies_path:
            runtime["cookiesPath"] = cookies_path
        return runtime or None

    async def _rpc(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        session = await self._get_session()
        url = f"{self.base_url}/rpc/{path.lstrip('/')}"
        body: dict[str, Any] = {"json": payload or {}}
        async with session.post(url, json=body) as resp:
            data = await resp.json(content_type=None)
            if resp.status >= 400:
                message = _extract_error(data) or f"VidBee API error ({resp.status})"
                raise VidBeeError(message)
            return _unwrap_json(data)

    async def get_video_info(self, url: str) -> VideoInfo:
        payload: dict[str, Any] = {"url": url}
        settings_payload = await self._runtime_settings_async()
        if settings_payload:
            payload["settings"] = settings_payload

        result = await self._rpc("videoInfo", payload)
        video = result.get("video", result)
        return VideoInfo(
            id=video.get("id", ""),
            title=video.get("title", "Без названия"),
            thumbnail=video.get("thumbnail"),
            duration=normalize_duration(video.get("duration")),
            uploader=video.get("uploader"),
            formats=video.get("formats", []),
            webpage_url=video.get("webpageUrl") or video.get("webpage_url"),
        )

    async def create_download(
        self,
        url: str,
        download_type: str,
        *,
        title: str | None = None,
        thumbnail: str | None = None,
        duration: int | None = None,
        format_string: str | None = None,
        container: str = "mp4",
    ) -> DownloadTask:
        payload: dict[str, Any] = {
            "url": url,
            "type": download_type,
            "containerFormat": container,
        }
        if title:
            payload["title"] = title
        if thumbnail:
            payload["thumbnail"] = thumbnail
        if duration is not None:
            payload["duration"] = duration
        if format_string:
            payload["format"] = format_string

        settings_payload = await self._runtime_settings_async()
        if settings_payload:
            payload["settings"] = settings_payload

        result = await self._rpc("downloads/create", payload)
        task_data = result.get("download", result)
        return _parse_task(task_data)

    async def cancel_download(self, task_id: str) -> bool:
        result = await self._rpc("downloads/cancel", {"id": task_id})
        return bool(result.get("cancelled", False))

    async def wait_completion(
        self,
        task_id: str,
        on_progress: Callable[[DownloadTask], Any] | None = None,
        poll_interval: float = 2.0,
    ) -> DownloadTask:
        """Wait for download via SSE, fall back to polling downloads/list."""
        try:
            return await self._wait_via_sse(task_id, on_progress)
        except (aiohttp.ClientError, TimeoutError, VidBeeError) as exc:
            logger.warning("SSE failed for task %s: %s, falling back to polling", task_id, exc)
            return await self._wait_via_polling(task_id, on_progress, poll_interval)

    async def _wait_via_sse(
        self,
        task_id: str,
        on_progress: Callable[[DownloadTask], Any] | None,
    ) -> DownloadTask:
        session = await self._get_session()
        url = f"{self.base_url}/events"
        last_task: DownloadTask | None = None

        async with session.get(url) as resp:
            if resp.status >= 400:
                raise VidBeeError(f"SSE unavailable ({resp.status})")

            buffer = ""
            async for chunk in resp.content.iter_any():
                buffer += chunk.decode("utf-8", errors="ignore")
                while "\n\n" in buffer:
                    block, buffer = buffer.split("\n\n", 1)
                    task = _parse_sse_block(block, task_id)
                    if task is None:
                        continue
                    last_task = task
                    if on_progress:
                        result = on_progress(task)
                        if hasattr(result, "__await__"):
                            await result
                    if task.status in ("completed", "error", "cancelled"):
                        if task.status == "completed":
                            return task
                        message = task.error or ERROR_MESSAGES.get(
                            task.error_category or "", "Ошибка загрузки."
                        )
                        raise VidBeeError(message, task.error_category)

        if last_task and last_task.status == "completed":
            return last_task
        raise VidBeeError("Соединение с VidBee прервано.")

    async def _wait_via_polling(
        self,
        task_id: str,
        on_progress: Callable[[DownloadTask], Any] | None,
        poll_interval: float,
    ) -> DownloadTask:
        import asyncio

        while True:
            result = await self._rpc("downloads/list")
            downloads = result.get("downloads", [])
            for item in downloads:
                if item.get("id") != task_id:
                    continue
                task = _parse_task(item)
                if on_progress:
                    result_cb = on_progress(task)
                    if hasattr(result_cb, "__await__"):
                        await result_cb
                if task.status == "completed":
                    return task
                if task.status in ("error", "cancelled"):
                    message = task.error or ERROR_MESSAGES.get(
                        task.error_category or "", "Ошибка загрузки."
                    )
                    raise VidBeeError(message, task.error_category)
            await asyncio.sleep(poll_interval)


def _unwrap_json(data: Any) -> Any:
    if isinstance(data, dict):
        if "json" in data:
            return data["json"]
        if "data" in data:
            return data["data"]
    return data


def _extract_error(data: Any) -> str | None:
    if not isinstance(data, dict):
        return None
    for key in ("message", "error", "reason"):
        if key in data and data[key]:
            return str(data[key])
    nested = data.get("json") or data.get("data")
    if isinstance(nested, dict):
        return _extract_error(nested)
    return None


def _parse_task(data: dict[str, Any]) -> DownloadTask:
    progress = data.get("progress") or {}
    return DownloadTask(
        id=data.get("id", ""),
        url=data.get("url", ""),
        title=data.get("title"),
        status=data.get("status", "pending"),
        download_path=data.get("downloadPath") or data.get("download_path"),
        saved_file_name=data.get("savedFileName") or data.get("saved_file_name"),
        error=data.get("error"),
        error_category=data.get("errorCategory") or data.get("error_category"),
        progress_percent=float(progress.get("percent", 0)),
        speed=data.get("speed") or progress.get("currentSpeed"),
        eta=progress.get("eta"),
    )


def _parse_sse_block(block: str, task_id: str) -> DownloadTask | None:
    event_name = "message"
    data_lines: list[str] = []
    for line in block.splitlines():
        if line.startswith("event:"):
            event_name = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].strip())

    if not data_lines:
        return None

    try:
        payload = json.loads("\n".join(data_lines))
    except json.JSONDecodeError:
        return None

    if event_name not in ("task-updated", "message"):
        return None

    task_data = payload.get("task", payload)
    if task_data.get("id") != task_id:
        return None
    return _parse_task(task_data)


def humanize_error(category: str | None, fallback: str | None = None) -> str:
    if category and category in ERROR_MESSAGES:
        return ERROR_MESSAGES[category]
    text = fallback or "Не удалось скачать видео."
    lower = text.lower()

    if "instagram" in lower and ("empty media" in lower or "cookies" in lower):
        return "Этот сервис временно недоступен — требуется настройка на стороне сервера."

    youtube_auth_markers = (
        "sign in to confirm your age",
        "inappropriate for some users",
        "use --cookies",
        "login required",
        "members-only",
        "private video",
    )
    if "youtube" in lower and any(m in lower for m in youtube_auth_markers):
        return (
            "Видео с возрастным ограничением.\n\n"
            "Cookies загружены, но YouTube их не принял — сессия устарела или "
            "экспортирована неправильно.\n\n"
            "<b>Как правильно:</b>\n"
            "1. Инкогнито → войти на youtube.com\n"
            "2. Открыть youtube.com/robots.txt\n"
            "3. Экспорт cookies → загрузить в админке → Синхронизировать\n"
            "4. Закрыть инкогнито и не заходить на YouTube в обычном браузере"
        )

    if any(m in lower for m in ("sign in", "login required", "cookies-from-browser", "use --cookies")):
        return (
            "Для этого видео нужна авторизация на сайте.\n\n"
            "Администратору: загрузите cookies в админке → <b>Сервисы</b>."
        )

    if len(text) > 300:
        return "Не удалось скачать видео. Попробуйте другую ссылку или формат."
    return text
