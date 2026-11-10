"""Measures for comparing pose models on a swimming clip.

Torso length is the primary stability measure. Arm and leg lengths change
when the body rolls, so they are not used. Wrist jerk is the other primary
measure: on the same clip, a higher value means the wrist landmark is jumping
around rather than moving with the stroke.

`next_video_timestamp` is the same rule the dashboard already uses
(pages/2_Dashboard.py: detect_for_video needs a strictly increasing
timestamp, and a retry uses last + 1 ms).
"""
import math


def next_video_timestamp(last_ms, requested_ms):
    """Return a timestamp strictly greater than last_ms.

    If the caller asks for a time that is not later, the result is last + 1,
    which is the retry used when a crop misses or a flipped frame is re-run.
    """
    if last_ms is None:
        return requested_ms
    if requested_ms <= last_ms:
        return last_ms + 1
    return requested_ms


def _mid(a, b):
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def torso_lengths(frames):
    """Pixel length from mid-shoulder to mid-hip for each frame that has all four."""
    lengths = []
    for frame in frames:
        needed = ("left_shoulder", "right_shoulder", "left_hip", "right_hip")
        if any(frame.get(name) is None for name in needed):
            continue
        shoulder = _mid(frame["left_shoulder"], frame["right_shoulder"])
        hip = _mid(frame["left_hip"], frame["right_hip"])
        length = _dist(shoulder, hip)
        if length > 0:
            lengths.append(length)
    return lengths


def coefficient_of_variation(values):
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    if mean == 0:
        return None
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(variance) / abs(mean)


def _jerk_of_series(points, fps):
    """Mean absolute jerk (px/s^3) along one wrist. Gaps break the series."""
    if fps <= 0:
        return None, 0
    dt = 1.0 / fps
    samples = []
    run = []
    for point in list(points) + [None]:
        if point is None:
            if len(run) >= 4:
                samples.extend(_jerks(run, dt))
            run = []
        else:
            run.append(point)
    if not samples:
        return None, 0
    return sum(samples) / len(samples), len(samples)


def _jerks(run, dt):
    vel = [((run[i + 1][0] - run[i][0]) / dt, (run[i + 1][1] - run[i][1]) / dt) for i in range(len(run) - 1)]
    acc = [((vel[i + 1][0] - vel[i][0]) / dt, (vel[i + 1][1] - vel[i][1]) / dt) for i in range(len(vel) - 1)]
    jerk = [((acc[i + 1][0] - acc[i][0]) / dt, (acc[i + 1][1] - acc[i][1]) / dt) for i in range(len(acc) - 1)]
    return [math.hypot(jx, jy) for jx, jy in jerk]


def wrist_jerk(frames, fps):
    """Mean absolute wrist jerk, averaged across the two wrists that have data."""
    totals = []
    counts = []
    for name in ("left_wrist", "right_wrist"):
        series = [frame.get(name) for frame in frames]
        value, count = _jerk_of_series(series, fps)
        if value is not None:
            totals.append(value)
            counts.append(count)
    if not totals:
        return None, 0
    return sum(totals) / len(totals), sum(counts)


def summarize(frames, fps, detected, total_frames):
    lengths = torso_lengths(frames)
    jerk, jerk_n = wrist_jerk(frames, fps)
    return {
        "frames": total_frames,
        "detected": detected,
        "detection_rate": (detected / total_frames) if total_frames else None,
        "torso_length_cv": coefficient_of_variation(lengths),
        "torso_samples": len(lengths),
        "wrist_jerk_px_per_s3": jerk,
        "wrist_jerk_samples": jerk_n,
    }
