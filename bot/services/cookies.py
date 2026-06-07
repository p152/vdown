import logging
from pathlib import Path

from bot.config import settings
from bot.services.vidbee import VidBeeClient

logger = logging.getLogger(__name__)

_synced_cookies_path: str | None = None


def cookies_file() -> Path:
    return Path(settings.vidbee_cookies_path)


def cookies_configured() -> bool:
    path = cookies_file()
    if not path.is_file():
        return False
    content = path.read_text(encoding="utf-8", errors="ignore").strip()
    return bool(content) and "instagram.com" in content.lower()


def get_cookies_path() -> str | None:
    if _synced_cookies_path:
        return _synced_cookies_path
    if cookies_file().is_file():
        return settings.vidbee_cookies_path
    return None


async def sync_cookies_to_vidbee(client: VidBeeClient | None = None) -> bool:
    """Upload cookies to VidBee and set global cookiesPath."""
    path = cookies_file()
    if not path.is_file():
        logger.info("Cookies file not found: %s", path)
        return False

    content = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not content:
        logger.warning("Cookies file is empty: %s", path)
        return False

    own_client = client is None
    if own_client:
        client = VidBeeClient()

    global _synced_cookies_path

    try:
        upload = await client._rpc(
            "files/uploadSettingsFile",
            {
                "kind": "cookies",
                "fileName": "cookies.txt",
                "content": content,
            },
        )
        cookies_path = upload.get("path", str(path))

        current = (await client._rpc("settings/get"))["settings"]
        current["cookiesPath"] = cookies_path
        await client._rpc("settings/set", {"settings": current})

        _synced_cookies_path = cookies_path
        logger.info("VidBee cookies synced: %s", cookies_path)
        return True
    except Exception:
        logger.exception("Failed to sync cookies to VidBee")
        return False
    finally:
        if own_client and client:
            await client.close()
