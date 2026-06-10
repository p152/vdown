from dataclasses import dataclass
from enum import StrEnum


class FormatChoice(StrEnum):
    AUTO = "auto"
    VIDEO_720 = "720"
    VIDEO_1080 = "1080"
    AUDIO = "audio"
    BEST = "best"


@dataclass(frozen=True)
class DownloadFormat:
    download_type: str
    format_string: str | None
    container: str


FORMAT_MAP: dict[FormatChoice, DownloadFormat] = {
    FormatChoice.AUTO: DownloadFormat(
        download_type="video",
        format_string="bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
        container="mp4",
    ),
    FormatChoice.VIDEO_720: DownloadFormat(
        download_type="video",
        format_string="bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
        container="mp4",
    ),
    FormatChoice.VIDEO_1080: DownloadFormat(
        download_type="video",
        format_string="bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
        container="mp4",
    ),
    FormatChoice.AUDIO: DownloadFormat(
        download_type="audio",
        format_string="ba/b",
        container="mp4",
    ),
    FormatChoice.BEST: DownloadFormat(
        download_type="video",
        format_string=None,
        container="auto",
    ),
}


def estimate_best_size_mb(formats: list[dict]) -> float | None:
    sizes = [
        f.get("filesize") or f.get("filesizeApprox")
        for f in formats
        if f.get("filesize") or f.get("filesizeApprox")
    ]
    if not sizes:
        return None
    return max(sizes) / (1024 * 1024)


def normalize_duration(seconds: int | float | None) -> int | None:
    if seconds is None:
        return None
    return int(round(seconds))


def format_duration(seconds: int | None) -> str:
    if not seconds:
        return "—"
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_size_mb(size_mb: float | None) -> str:
    if size_mb is None:
        return "—"
    if size_mb >= 1024:
        return f"{size_mb / 1024:.1f} ГБ"
    return f"{size_mb:.0f} МБ"
