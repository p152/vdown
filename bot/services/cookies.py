"""Backward-compatible re-exports. Prefer bot.services.cookies_manager."""

from bot.services.cookies_manager import (
    cookies_configured,
    cookies_master_path as cookies_file,
    get_cookies_path,
    sync_cookies_to_vidbee,
)

__all__ = ["cookies_configured", "cookies_file", "get_cookies_path", "sync_cookies_to_vidbee"]
