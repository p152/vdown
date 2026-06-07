import re

URL_PATTERN = re.compile(
    r"https?://[^\s<>\"']+",
    re.IGNORECASE,
)


def extract_urls(text: str) -> list[str]:
    return URL_PATTERN.findall(text)
