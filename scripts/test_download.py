#!/usr/bin/env python3
"""E2E download test via VidBee API inside docker network."""
import asyncio
import sys
from pathlib import Path

from bot.services.vidbee import VidBeeClient, VidBeeError


async def test_url(label: str, url: str) -> bool:
    client = VidBeeClient()
    print(f"\n=== {label} ===")
    print(f"URL: {url}")
    try:
        info = await client.get_video_info(url)
        print(f"OK videoInfo: {info.title!r} ({info.duration}s, {len(info.formats)} formats)")

        task = await client.create_download(
            url,
            "video",
            title=info.title,
            duration=info.duration,
            format_string="bv*[height<=480]+ba/b",
            container="mp4",
        )
        print(f"OK create: task_id={task.id} status={task.status}")

        def on_progress(t):
            print(f"  progress: {t.progress_percent:.0f}% status={t.status}")

        completed = await client.wait_completion(task.id, on_progress=on_progress, poll_interval=3.0)

        from bot.config import settings
        from bot.services.queue import _resolve_file_path

        path = _resolve_file_path(completed.download_path, completed.saved_file_name)

        if not path or not Path(path).is_file():
            print(f"FAIL: file not found after download (path={path!r})")
            return False

        size = Path(path).stat().st_size
        print(f"OK completed: {path} ({size / 1024 / 1024:.2f} MB)")
        Path(path).unlink(missing_ok=True)
        return True

    except VidBeeError as exc:
        print(f"FAIL VidBeeError: {exc}")
        return False
    except Exception as exc:
        print(f"FAIL {type(exc).__name__}: {exc}")
        return False
    finally:
        await client.close()


async def main() -> int:
    tests = [
        ("YouTube", "https://www.youtube.com/watch?v=jNQXAC9IVRw"),  # "Me at the zoo" ~19s
        ("Instagram", "https://www.instagram.com/reel/C0BdxgqrQix/"),
    ]
    results = []
    for label, url in tests:
        ok = await test_url(label, url)
        results.append((label, ok))

    print("\n=== SUMMARY ===")
    for label, ok in results:
        print(f"{'PASS' if ok else 'FAIL'}: {label}")

    return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
