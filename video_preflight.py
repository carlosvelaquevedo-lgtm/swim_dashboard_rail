"""Framing and tracking geometry shared by the 2D dashboard and the 3D lab.

No Streamlit and no MediaPipe. Tests pass a fake detector. The dashboard
calls these helpers and does the actual pose detection itself.
"""

MAX_COAST_FRAMES = 12
TILE_WIDTH_FRACTION = 0.60
MIN_SWIMMER_SPAN = 0.18
ANALYSIS_WINDOW_MAX = 15.0
ANALYSIS_WINDOW_MIN = 6.0

# A report is saved only after normalization and the coverage gate both
# succeed. A rejected clip must not write meta.json, which is what spends
# the paid credit.
def should_persist_report(normalized_ok, coverage_ok, framing_blocked=False):
    return bool(normalized_ok and coverage_ok and not framing_blocked)


def sample_fractions():
    return (0.25, 0.50, 0.75)


def sample_times(start_s, window_s):
    """Three instants inside the selected analysis window."""
    window = max(0.0, float(window_s or 0.0))
    start = max(0.0, float(start_s or 0.0))
    return tuple(start + window * fraction for fraction in sample_fractions())


def span_fraction(xs, ys, frame_w, frame_h):
    """Largest side of the landmark box, as a fraction of the frame's short side."""
    if not xs or not ys or frame_w <= 0 or frame_h <= 0:
        return None
    box_w = max(xs) - min(xs)
    box_h = max(ys) - min(ys)
    short = float(min(frame_w, frame_h))
    return max(box_w, box_h) / short


def framing_verdict(spans, min_span=MIN_SWIMMER_SPAN):
    """'ok', 'too_small', 'no_swimmer', or 'skipped' when every sample failed closed."""
    if not spans or all(span is None for span in spans):
        return "skipped"
    present = [span for span in spans if span is not None]
    if not present:
        return "no_swimmer"
    if max(present) <= 0:
        return "no_swimmer"
    if max(present) < min_span:
        return "too_small"
    return "ok"


def next_timestamp(last_ms):
    """MediaPipe VIDEO mode rejects a timestamp that is not strictly increasing."""
    return int(last_ms) + 1


def tile_boxes(width, height, fraction=TILE_WIDTH_FRACTION):
    """Three overlapping horizontal zoom tiles: left, center, right."""
    width = int(width)
    height = int(height)
    if width < 2 or height < 2:
        return ()
    tile_w = max(2, int(round(width * fraction)))
    tile_w = min(tile_w, width)
    starts = [0, max(0, (width - tile_w) // 2), max(0, width - tile_w)]
    boxes = []
    for start in starts:
        box = (start, 0, start + tile_w, height)
        if box not in boxes:
            boxes.append(box)
    return tuple(boxes)


def should_probe_tiles(untracked_frames):
    """Every third frame that still has no swimmer."""
    frames = int(untracked_frames)
    return frames > 0 and frames % 3 == 0


def coast_track(center, size, misses):
    """Hold the last swimmer window through a miss.

    The window widens by 15% on each miss. The center is cleared only after
    MAX_COAST_FRAMES consecutive misses, so one splash frame does not drop
    the track back to a full-frame search.
    """
    if center is None or size is None:
        return None, None, 0
    misses = int(misses) + 1
    if misses >= MAX_COAST_FRAMES:
        return None, None, 0
    return center, float(size) * 1.15, misses
