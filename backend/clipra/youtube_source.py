"""Owner-authorized public YouTube videos and bounded livestream recordings.

This uses the open-source yt-dlp + FFmpeg stack, not Higgsfield or paid AI.
No cookies, sign-in bypass, private video access, or DRM circumvention.
Only the validated YouTube video ID is passed to the downloader.
"""
from __future__ import annotations

import os
import resource
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .media import verify_decodable, sha256_file, MediaError


class YouTubeImportError(RuntimeError):
    pass


def _limits() -> tuple[int, int, int]:
    bytes_cap = max(50 * 1024 * 1024, min(
        int(os.getenv("MAX_YOUTUBE_BYTES", str(750 * 1024 * 1024))),
        2 * 1024 * 1024 * 1024))
    duration_cap = max(60, min(int(os.getenv("MAX_YOUTUBE_SECONDS", "14400")), 21600))
    live_seconds = max(30, min(int(os.getenv("MAX_LIVE_RECORD_SECONDS", "300")), 900))
    return bytes_cap, duration_cap, live_seconds


def _cap_files(limit: int) -> None:
    resource.setrlimit(resource.RLIMIT_FSIZE, (limit, limit))


def download_authorized_youtube(video_id: str, root: Path) -> dict:
    import re
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        raise YouTubeImportError("Invalid YouTube video ID.")
    try:
        from yt_dlp import YoutubeDL
        from yt_dlp.utils import DownloadError
    except ImportError as exc:
        raise YouTubeImportError("The free YouTube downloader is not installed.") from exc

    bytes_cap, duration_cap, live_seconds = _limits()
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        with YoutubeDL({
            "quiet": True, "no_warnings": True, "noplaylist": True,
            "skip_download": True, "cachedir": False,
            "socket_timeout": 20, "retries": 1, "ignoreerrors": False,
        }) as inspect:
            info = inspect.extract_info(url, download=False)
    except (DownloadError, Exception) as exc:
        raise YouTubeImportError(
            "YouTube could not supply this video to the server. "
            "Try downloading your original recording from YouTube Studio and uploading the file."
        ) from exc

    if not isinstance(info, dict) or info.get("_type") == "playlist":
        raise YouTubeImportError("Single public video required; playlists are unsupported.")
    live = bool(info.get("is_live") or info.get("live_status") == "is_live")
    length = info.get("duration")
    if not live and length is not None and float(length) > duration_cap:
        raise YouTubeImportError(f"Video is longer than the {duration_cap // 3600}h import limit.")
    if info.get("availability") in ("private", "premium_only", "subscriber_only"):
        raise YouTubeImportError("Private and restricted videos are not supported.")

    (root / "uploads").mkdir(parents=True, exist_ok=True)
    (root / "originals").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="youtube_", dir=root / "uploads") as folder:
        scratch = Path(folder)
        command = [
            sys.executable, "-m", "yt_dlp",
            "--no-playlist", "--no-cache-dir", "--no-progress",
            "--no-warnings", "--no-colors",
            "--format", "bv*[height<=720]+ba/b[height<=720]/b",
            "--merge-output-format", "mp4",
            "--max-filesize", str(bytes_cap),
            "--socket-timeout", "20",
            "--retries", "1", "--fragment-retries", "1",
            "--output", str(scratch / "authorized.%(ext)s"),
        ]
        if live:
            # ffmpeg stops the livestream download after a strict time window.
            # Livestream import captures a recent section, not a complete broadcast.
            command.extend(["--download-sections", f"*0-{live_seconds}"])
        command.append(url)
        try:
            done = subprocess.run(
                command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=live_seconds + 240 if live else 1000,
                check=False,
                preexec_fn=lambda: _cap_files(bytes_cap),
            )
        except subprocess.TimeoutExpired as exc:
            raise YouTubeImportError(
                "YouTube import timed out; no clip was created. Use the original file instead."
            ) from exc
        if done.returncode != 0:
            raise YouTubeImportError(
                "YouTube downloader could not access this public video from the hosting server. "
                "Upload your original video file for reliable free clipping."
            )
        files = sorted(
            [p for p in scratch.iterdir()
             if p.is_file() and p.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm", ".m4v"}],
            key=lambda p: p.stat().st_size, reverse=True)
        if not files:
            raise YouTubeImportError("The downloader produced no playable source video.")
        source = files[0]
        if source.stat().st_size > bytes_cap:
            raise YouTubeImportError("Downloaded file exceeded the safe free hosting limit.")
        try:
            meta = verify_decodable(source)
        except MediaError as exc:
            raise YouTubeImportError(f"Downloaded media failed validation: {exc}") from exc
        import uuid
        destination = root / "originals" / f"{uuid.uuid4().hex}.media"
        shutil.move(str(source), str(destination))
        return {
            "path": destination,
            "filename": f"youtube-{video_id}{source.suffix.lower()}",
            "sha256": sha256_file(destination),
            "size": destination.stat().st_size,
            "duration": meta["duration"],
            "width": meta["width"], "height": meta["height"],
            "fps": meta["fps"], "has_audio": meta["has_audio"],
            "youtube_url": url,
            "source_status": "live_capture" if live else "video_or_replay",
        }
