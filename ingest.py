"""Upload and analysis-cleanup helpers.

No Streamlit import: the dashboard calls these, and tests can import them
without starting the app.
"""
import os
import shutil
import subprocess
import tempfile

MAX_UPLOAD_BYTES = 100 * 1024 * 1024
PROBE_TIMEOUT_SECONDS = 15


def write_upload_to_temp(uploaded, suffix=".mp4") -> str:
    """Stream an uploaded file to disk. Does not call getvalue()."""
    uploaded.seek(0)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        shutil.copyfileobj(uploaded, tmp)
    except Exception:
        tmp.close()
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise
    tmp.close()
    return tmp.name


def probe_duration_seconds(path: str, timeout: int = PROBE_TIMEOUT_SECONDS):
    """Return the container duration in seconds, or None if ffprobe fails."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "format=duration", "-of", "csv=p=0",
                path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        text = result.stdout.decode().strip()
        return float(text) if text else None
    except Exception:
        return None


def cached_duration(cache: dict, uploaded, ffprobe_available: bool):
    """Duration for this upload, probed at most once per name and size.

    The probe temp file is deleted before this returns, including when
    ffprobe fails or times out. A later call for the same name and size
    reads `cache` and does not touch the disk.
    """
    key = f"{uploaded.name}:{uploaded.size}"
    if key in cache:
        return cache[key]
    if not ffprobe_available:
        cache[key] = None
        return None
    path = write_upload_to_temp(uploaded)
    try:
        duration = probe_duration_seconds(path)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    cache[key] = duration
    return duration


def encode_slowmo(report_mode: str) -> bool:
    """Swimmer reports never show the slow-motion video, so don't encode it."""
    return report_mode == "coach"


def release_analysis_resources(
    cap=None,
    av_container=None,
    slowmo_container=None,
    writer=None,
    analyzer=None,
    paths=(),
):
    """Close every handle, then delete temp files. Close errors do not skip the rest."""
    for obj, method in (
        (cap, "release"),
        (av_container, "close"),
        (slowmo_container, "close"),
        (writer, "release"),
        (analyzer, "close"),
    ):
        if obj is None:
            continue
        try:
            getattr(obj, method)()
        except Exception:
            pass
    for path in paths:
        if not path:
            continue
        try:
            if os.path.exists(path):
                os.unlink(path)
        except OSError:
            pass
