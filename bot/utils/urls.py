import re
from urllib.parse import urlparse

URL_PATTERN = re.compile(
    r"https?://[^\s<>\"']+",
    re.IGNORECASE,
)


def extract_urls(text: str) -> list[str]:
    return URL_PATTERN.findall(text)


def extract_domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host or "unknown"
    except Exception:
        return "unknown"
