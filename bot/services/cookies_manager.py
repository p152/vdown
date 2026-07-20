import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from bot.config import settings
from bot.services.platform_catalog import PLATFORMS, AuthType, Platform, get_platform
from bot.services.vidbee import VidBeeClient

logger = logging.getLogger(__name__)

_synced_cookies_path: str | None = None

NETSCAPE_HEADER = "# Netscape HTTP Cookie File"


def cookies_master_path() -> Path:
    return Path(settings.vidbee_cookies_path)


def platforms_dir() -> Path:
    return cookies_master_path().parent / "platforms"


def _read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _cookie_line_domain(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    parts = stripped.split("\t")
    if len(parts) < 1:
        return None
    return parts[0].lstrip(".").lower()


def _domains_in_content(content: str) -> set[str]:
    found: set[str] = set()
    for line in content.splitlines():
        domain = _cookie_line_domain(line)
        if domain:
            found.add(domain)
    return found


def _platform_has_cookies(platform: Platform, cookie_domains: set[str]) -> bool:
    for pattern in platform.domains:
        pattern = pattern.lower()
        for domain in cookie_domains:
            if domain == pattern or domain.endswith("." + pattern):
                return True
    return False


def platform_cookie_file(platform_id: str) -> Path:
    return platforms_dir() / f"{platform_id}.txt"


def list_platform_statuses() -> list[dict]:
    items: list[dict] = []
    for platform in PLATFORMS:
        configured = _platform_has_cookies(platform, _platform_cookie_domains(platform))
        if platform.auth == "none":
            status = "ready"
        elif configured:
            status = "ready"
        elif platform.auth == "cookies":
            status = "required"
        else:
            status = "optional"
        items.append(
            {
                "id": platform.id,
                "name": platform.name,
                "domains": list(platform.domains),
                "auth": platform.auth,
                "instructions": platform.instructions,
                "configured": configured,
                "status": status,
                "has_file": platform_cookie_file(platform.id).is_file(),
                "updated_at": _file_mtime(platform_cookie_file(platform.id)),
            }
        )
    return items


def _file_mtime(path: Path) -> str | None:
    if not path.is_file():
        return None
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _platform_cookie_domains(platform: Platform) -> set[str]:
    domains = _domains_in_content(_read_text(cookies_master_path()))
    platform_file = platform_cookie_file(platform.id)
    if platform_file.is_file():
        domains |= _domains_in_content(_read_text(platform_file))
    return domains


def is_platform_ready(platform: Platform) -> bool:
    if platform.auth == "none":
        return True
    if platform.auth == "optional_cookies":
        return True
    return _platform_has_cookies(platform, _platform_cookie_domains(platform))


def is_url_ready(url: str) -> tuple[bool, Platform | None, str | None]:
    from bot.services.platform_catalog import get_platform_for_url

    platform = get_platform_for_url(url)
    if platform is None:
        return True, None, None
    if is_platform_ready(platform):
        return True, platform, None
    return False, platform, platform.instructions


def cookies_configured() -> bool:
    """Backward compat: Instagram cookies present."""
    platform = get_platform("instagram")
    if platform is None:
        return False
    return is_platform_ready(platform)


def get_cookies_path() -> str | None:
    if _synced_cookies_path:
        return _synced_cookies_path
    path = cookies_master_path()
    if path.is_file() and path.read_text(encoding="utf-8", errors="ignore").strip():
        return str(path)
    return None


def _merge_platform_into_master(platform: Platform, platform_content: str) -> str:
    platform_domains = {d.lower() for d in platform.domains}
    existing = _read_text(cookies_master_path())
    kept_lines: list[str] = []
    header_seen = False
    for line in existing.splitlines():
        if line.strip().startswith("# Netscape"):
            if not header_seen:
                kept_lines.append(NETSCAPE_HEADER)
                header_seen = True
            continue
        domain = _cookie_line_domain(line)
        if domain and any(domain == p or domain.endswith("." + p) for p in platform_domains):
            continue
        kept_lines.append(line)

    if not header_seen:
        kept_lines.insert(0, NETSCAPE_HEADER)

    new_lines = [line for line in platform_content.splitlines() if line.strip()]
    if new_lines and new_lines[0].strip().startswith("# Netscape"):
        new_lines = new_lines[1:]

    merged = "\n".join(kept_lines + new_lines).strip() + "\n"
    return merged


def rebuild_master_from_platform_files() -> bool:
    platforms_dir().mkdir(parents=True, exist_ok=True)
    lines = [NETSCAPE_HEADER]
    any_data = False
    for platform in PLATFORMS:
        path = platform_cookie_file(platform.id)
        if not path.is_file():
            continue
        content = _read_text(path)
        for line in content.splitlines():
            if _cookie_line_domain(line):
                lines.append(line)
                any_data = True
    if not any_data:
        master = cookies_master_path()
        if master.is_file():
            master.unlink()
        return False
    cookies_master_path().parent.mkdir(parents=True, exist_ok=True)
    cookies_master_path().write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


async def save_platform_cookies(platform_id: str, content: str) -> dict:
    platform = get_platform(platform_id)
    if platform is None:
        raise ValueError("Unknown platform")
    if platform.auth == "none":
        raise ValueError("Platform does not require cookies")

    content = content.strip()
    if not content:
        raise ValueError("Empty cookies file")
    if len(content.encode("utf-8")) > 500_000:
        raise ValueError("File too large (max 500KB)")

    cookie_domains = _domains_in_content(content)
    if not _platform_has_cookies(platform, cookie_domains):
        raise ValueError(
            f"Cookies file does not contain domains for {platform.name}: "
            + ", ".join(platform.domains)
        )

    platforms_dir().mkdir(parents=True, exist_ok=True)
    platform_cookie_file(platform_id).write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8")

    merged = _merge_platform_into_master(platform, content)
    cookies_master_path().parent.mkdir(parents=True, exist_ok=True)
    cookies_master_path().write_text(merged, encoding="utf-8")

    synced = await sync_cookies_to_vidbee()
    return {"ok": True, "synced": synced, "platform_id": platform_id}


async def delete_platform_cookies(platform_id: str) -> dict:
    platform = get_platform(platform_id)
    if platform is None:
        raise ValueError("Unknown platform")

    path = platform_cookie_file(platform_id)
    if path.is_file():
        path.unlink()

    platform_domains = {d.lower() for d in platform.domains}
    existing = _read_text(cookies_master_path())
    kept_lines: list[str] = []
    header_seen = False
    for line in existing.splitlines():
        if line.strip().startswith("# Netscape"):
            if not header_seen:
                kept_lines.append(NETSCAPE_HEADER)
                header_seen = True
            continue
        domain = _cookie_line_domain(line)
        if domain and any(domain == p or domain.endswith("." + p) for p in platform_domains):
            continue
        if _cookie_line_domain(line):
            kept_lines.append(line)

    if len(kept_lines) <= 1:
        master = cookies_master_path()
        if master.is_file():
            master.unlink()
    else:
        cookies_master_path().write_text("\n".join(kept_lines) + "\n", encoding="utf-8")

    synced = await sync_cookies_to_vidbee()
    return {"ok": True, "synced": synced}


async def sync_cookies_to_vidbee(client: VidBeeClient | None = None) -> bool:
    path = cookies_master_path()
    if not path.is_file():
        logger.info("Master cookies file not found: %s", path)
        return False

    content = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not content:
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


async def get_vidbee_settings() -> dict:
    client = VidBeeClient()
    try:
        result = await client._rpc("settings/get")
        settings_data = result.get("settings", result)
        return {
            "cookiesPath": settings_data.get("cookiesPath", ""),
            "proxy": settings_data.get("proxy", ""),
            "configPath": settings_data.get("configPath", ""),
            "maxConcurrentDownloads": settings_data.get("maxConcurrentDownloads"),
        }
    finally:
        await client.close()


async def set_vidbee_proxy(proxy: str) -> dict:
    client = VidBeeClient()
    try:
        current = (await client._rpc("settings/get"))["settings"]
        current["proxy"] = proxy.strip()
        await client._rpc("settings/set", {"settings": current})
        return {"ok": True, "proxy": current["proxy"]}
    finally:
        await client.close()
