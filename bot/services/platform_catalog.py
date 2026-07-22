from dataclasses import dataclass
from typing import Literal

from bot.utils.urls import extract_domain

AuthType = Literal["none", "cookies", "optional_cookies"]


@dataclass(frozen=True)
class Platform:
    id: str
    name: str
    domains: tuple[str, ...]
    auth: AuthType
    instructions: str


PLATFORMS: tuple[Platform, ...] = (
    Platform(
        id="youtube",
        name="YouTube",
        domains=("youtube.com", "youtu.be", "youtube-nocookie.com", "google.com", "accounts.google.com"),
        auth="optional_cookies",
        instructions=(
            "Для age-restricted видео нужны cookies YouTube.\n"
            "1. Откройте инкогнито → войдите на youtube.com\n"
            "2. Перейдите на youtube.com/robots.txt\n"
            "3. Экспортируйте cookies (Get cookies.txt LOCALLY)\n"
            "4. Закройте инкогнито — не открывайте YouTube в обычном браузере"
        ),
    ),
    Platform(
        id="tiktok",
        name="TikTok",
        domains=("tiktok.com", "vm.tiktok.com"),
        auth="none",
        instructions="Обычно работает без настройки. При блокировке — cookies с tiktok.com.",
    ),
    Platform(
        id="instagram",
        name="Instagram",
        domains=("instagram.com",),
        auth="cookies",
        instructions=(
            "Обязательны cookies. Экспорт через «Get cookies.txt LOCALLY» "
            "на instagram.com после входа в аккаунт."
        ),
    ),
    Platform(
        id="twitter",
        name="Twitter / X",
        domains=("twitter.com", "x.com", "mobile.twitter.com"),
        auth="optional_cookies",
        instructions="Публичные посты — без настройки. Приватное / login wall — cookies с x.com.",
    ),
    Platform(
        id="vk",
        name="VK",
        domains=("vk.com", "vkvideo.ru"),
        auth="optional_cookies",
        instructions="Публичное видео — без настройки. Закрытые — cookies с vk.com.",
    ),
    Platform(
        id="facebook",
        name="Facebook",
        domains=("facebook.com", "fb.watch"),
        auth="cookies",
        instructions="Нужны cookies с facebook.com после входа.",
    ),
    Platform(
        id="reddit",
        name="Reddit",
        domains=("reddit.com", "redd.it", "v.redd.it"),
        auth="none",
        instructions="Обычно работает без настройки.",
    ),
    Platform(
        id="twitch",
        name="Twitch",
        domains=("twitch.tv", "clips.twitch.tv"),
        auth="optional_cookies",
        instructions="Клипы и VOD — без настройки. Subscriber-only — cookies с twitch.tv.",
    ),
)


def get_platform(platform_id: str) -> Platform | None:
    for platform in PLATFORMS:
        if platform.id == platform_id:
            return platform
    return None


def get_platform_for_domain(domain: str) -> Platform | None:
    domain = domain.lower()
    for platform in PLATFORMS:
        for pattern in platform.domains:
            if domain == pattern or domain.endswith("." + pattern):
                return platform
    return None


def get_platform_for_url(url: str) -> Platform | None:
    return get_platform_for_domain(extract_domain(url))
