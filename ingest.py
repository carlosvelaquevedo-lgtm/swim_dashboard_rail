"""Upload and analysis-cleanup helpers.

No Streamlit import: the dashboard calls these, and tests can import them
without starting the app.
"""
import json
import os
import shutil
import subprocess
import tempfile

MAX_UPLOAD_BYTES = 500 * 1024 * 1024
PROBE_TIMEOUT_SECONDS = 15
NORMALIZE_TIMEOUT_SECONDS = 180
MAX_LONG_SIDE = 1920

UPLOAD_EXTENSIONS = (
    "mp4", "mov", "m4v", "avi", "mkv", "webm", "mts", "m2ts",
    "3gp", "wmv", "mpg", "mpeg", "lrv",
)


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


def upload_suffix(name: str) -> str:
    """Keep a known container extension so ffmpeg can sniff the upload."""
    ext = os.path.splitext(name or "")[1].lower().lstrip(".")
    if ext in UPLOAD_EXTENSIONS:
        return "." + ext
    return ".mp4"


def _float_or_none(value):
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number < 0:
        return None
    return number


def _frame_rate(value):
    if not value or value in ("0/0", "N/A"):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    text = str(value)
    if "/" in text:
        num, den = text.split("/", 1)
        try:
            den_f = float(den)
            return float(num) / den_f if den_f else None
        except ValueError:
            return None
    return _float_or_none(text)


def _rotation_degrees(stream: dict) -> int:
    tags = stream.get("tags") or {}
    raw = tags.get("rotate")
    if raw is not None:
        try:
            return int(round(float(raw))) % 360
        except (TypeError, ValueError):
            pass
    for side in stream.get("side_data_list") or []:
        if "rotation" not in side:
            continue
        try:
            number = float(side.get("rotation"))
        except (TypeError, ValueError):
            continue
        if number != number:
            continue
        # ffprobe reports the display matrix as a clockwise-negative angle.
        return int(round(-number)) % 360
    return 0


def display_dimensions(width, height, rotation):
    """Swap the coded size when the display rotation is 90 or 270 degrees."""
    if int(rotation) % 360 in (90, 270):
        return height, width
    return width, height


def _is_gopro(payload: dict, video: dict) -> bool:
    tags = video.get("tags") or {}
    blob = " ".join(str(tags.get(key, "")) for key in ("encoder", "handler_name", "com.apple.quicktime.model"))
    if "gopro" in blob.lower():
        return True
    for stream in payload.get("streams") or []:
        if str(stream.get("codec_tag_string") or "").lower() == "gpmd":
            return True
        name = str(stream.get("codec_name") or "")
        if name.lower() == "bin_data" and "gopro" in str(stream.get("tags") or {}).lower():
            return True
    return False


def probe_video_metadata(path: str, timeout: int = PROBE_TIMEOUT_SECONDS):
    """One JSON ffprobe pass.

    Returns None when the file has no real video stream (audio-only, or only
    a cover-art thumbnail). Duration falls back from the video stream to the
    container so a "N/A" string does not raise.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-print_format", "json",
                "-show_format", "-show_streams", path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        payload = json.loads(result.stdout.decode() or "{}")
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None

    video = None
    for stream in payload.get("streams") or []:
        if stream.get("codec_type") != "video":
            continue
        disposition = stream.get("disposition") or {}
        if disposition.get("attached_pic"):
            continue
        video = stream
        break
    if video is None:
        return None

    width = int(video.get("width") or 0)
    height = int(video.get("height") or 0)
    rotation = _rotation_degrees(video)
    display_w, display_h = display_dimensions(width, height, rotation)
    duration = _float_or_none(video.get("duration"))
    if duration is None:
        duration = _float_or_none((payload.get("format") or {}).get("duration"))
    frames = video.get("nb_frames")
    try:
        nb_frames = int(frames) if frames not in (None, "N/A") else 0
    except (TypeError, ValueError):
        nb_frames = 0
    return {
        "video_stream_index": int(video.get("index") or 0),
        "codec": video.get("codec_name") or "",
        "pix_fmt": video.get("pix_fmt") or "",
        "width": width,
        "height": height,
        "display_w": display_w,
        "display_h": display_h,
        "rotation": rotation,
        "src_fps": _frame_rate(video.get("avg_frame_rate")) or _frame_rate(video.get("r_frame_rate")),
        "duration": duration,
        "nb_frames": nb_frames,
        "is_gopro": _is_gopro(payload, video),
    }


def _output_frame_readable(path: str) -> bool:
    meta = probe_video_metadata(path)
    if not meta:
        return False
    if meta["nb_frames"] <= 0 and not (meta["duration"] and meta["duration"] > 0):
        return False
    try:
        import cv2
    except ImportError:
        return True
    cap = cv2.VideoCapture(path)
    try:
        ok, frame = cap.read()
    finally:
        cap.release()
    return bool(ok and frame is not None)


def normalize_video_to_cfr(
    input_path: str,
    start_s: float = 0.0,
    duration_s: float = None,
    playback_speed: float = 1.0,
    orientation: str = "auto",
    undistort: bool = False,
    max_long_side: int = MAX_LONG_SIDE,
    video_stream_index: int = None,
    timeout: int = NORMALIZE_TIMEOUT_SECONDS,
):
    """Re-encode one video stream to 1x 30fps yuv420p H.264.

    Returns (path, ok, message). On failure the original path is returned and
    ok is False, so the caller can reject the upload instead of analyzing it.
    `-ss` and `-t` are input options, so a long GoPro file is seeked before
    the 4K frames are decoded.
    """
    meta = probe_video_metadata(input_path)
    if meta is None and video_stream_index is None:
        return input_path, False, "no video stream"
    index = video_stream_index if video_stream_index is not None else meta["video_stream_index"]
    speed = float(playback_speed or 1.0)
    if speed <= 0:
        speed = 1.0

    filters = []
    if orientation == "flip180":
        filters.append("hflip,vflip")
    elif orientation == "rot90cw":
        filters.append("transpose=1")
    elif orientation == "rot90ccw":
        filters.append("transpose=2")
    if undistort:
        filters.append("lenscorrection=k1=-0.18:k2=0.02")
    if abs(speed - 1.0) > 1e-6:
        filters.append(f"setpts={speed:.6f}*(PTS-STARTPTS)")
    side = int(max_long_side)
    filters.append(
        f"scale='if(gt(iw,ih),min(iw,{side}),-2)':'if(gt(iw,ih),-2,min(ih,{side}))'"
    )
    filters.append("fps=30")

    out_path = tempfile.NamedTemporaryFile(delete=False, suffix="_cfr_h264.mp4").name
    command = ["ffmpeg", "-hide_banner", "-v", "error", "-err_detect", "ignore_err", "-threads", "0"]
    if start_s and start_s > 0:
        command.extend(["-ss", f"{float(start_s):.3f}"])
    if duration_s is not None and duration_s > 0:
        command.extend(["-t", f"{float(duration_s):.3f}"])
    command.extend([
        "-i", input_path,
        "-map", f"0:{int(index)}",
        "-an", "-sn", "-dn", "-map_metadata", "-1",
        "-vf", ",".join(filters),
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-pix_fmt", "yuv420p", "-fps_mode", "cfr", "-r", "30",
        "-movflags", "+faststart", "-y", out_path,
    ])
    try:
        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        try:
            os.unlink(out_path)
        except OSError:
            pass
        return input_path, False, type(exc).__name__
    if result.returncode != 0 or not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        try:
            os.unlink(out_path)
        except OSError:
            pass
        detail = (result.stderr or b"").decode(errors="replace")[-400:]
        return input_path, False, detail or "ffmpeg failed"
    if not _output_frame_readable(out_path):
        try:
            os.unlink(out_path)
        except OSError:
            pass
        return input_path, False, "normalized file has no readable frame"
    return out_path, True, "ok"


def extract_preview_jpeg(path: str, t_seconds: float, max_side: int = 480, timeout: int = 20):
    """One JPEG at t, scaled down. None when ffmpeg cannot decode that instant."""
    side = int(max_side)
    scale = f"scale='if(gt(iw,ih),min(iw,{side}),-2)':'if(gt(iw,ih),-2,min(ih,{side}))'"
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-v", "error",
                "-ss", f"{max(0.0, float(t_seconds)):.3f}", "-i", path,
                "-frames:v", "1", "-vf", scale,
                "-f", "image2", "-c:v", "mjpeg", "pipe:1",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0 or not result.stdout:
        return None
    return result.stdout
