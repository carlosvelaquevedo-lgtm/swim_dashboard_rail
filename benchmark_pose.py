"""Compare MediaPipe Pose Landmarker Lite and Heavy on one or more clips.

Usage:
    python3 benchmark_pose.py clip_close.mp4 clip_wide.mp4

Prints one JSON object per model per clip. Torso-length variation and wrist
jerk are the numbers to compare. Limb lengths are not reported, because they
change as the swimmer rolls.

This does not change which model the app uses. The two decision clips are not
in the repo, so the default stays as it is in the dashboard until those
numbers exist.

Timestamps follow the dashboard: each frame asks for a later timestamp, and a
retry (crop miss, or the same timestamp submitted twice) uses the previous
timestamp plus 1 ms.
"""
import argparse
import json
import os
import sys
import urllib.request

import cv2

import pose_quality

LITE_URL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task"
HEAVY_URL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task"
NAMES = {
    11: "left_shoulder",
    12: "right_shoulder",
    15: "left_wrist",
    16: "right_wrist",
    23: "left_hip",
    24: "right_hip",
}


def _model_path(url, filename):
    directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".pose_models")
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, filename)
    if not os.path.exists(path) or os.path.getsize(path) < 1000:
        print(f"downloading {filename}", file=sys.stderr)
        urllib.request.urlretrieve(url, path)
    return path


def _run_clip(video_path, model_path, label, max_frames=None):
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision

    options = vision.PoseLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=model_path),
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.35,
        min_pose_presence_confidence=0.35,
        min_tracking_confidence=0.35,
    )
    landmarker = vision.PoseLandmarker.create_from_options(options)
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frames = []
    detected = 0
    total = 0
    last_ms = None
    try:
        while cap.isOpened():
            ok, frame = cap.read()
            if not ok:
                break
            total += 1
            if max_frames is not None and total > max_frames:
                total -= 1
                break
            requested = int(round((total - 1) * 1000.0 / fps))
            timestamp = pose_quality.next_video_timestamp(last_ms, requested)
            last_ms = timestamp
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            try:
                result = landmarker.detect_for_video(image, timestamp)
            except Exception:
                timestamp = pose_quality.next_video_timestamp(last_ms, last_ms)
                last_ms = timestamp
                result = landmarker.detect_for_video(image, timestamp)
            height, width = frame.shape[:2]
            joints = {name: None for name in NAMES.values()}
            if result.pose_landmarks:
                detected += 1
                landmarks = result.pose_landmarks[0]
                for index, name in NAMES.items():
                    landmark = landmarks[index]
                    joints[name] = (landmark.x * width, landmark.y * height)
            frames.append(joints)
    finally:
        cap.release()
        landmarker.close()
    summary = pose_quality.summarize(frames, fps, detected, total)
    summary["model"] = label
    summary["clip"] = os.path.basename(video_path)
    summary["fps"] = fps
    return summary


def main(argv):
    parser = argparse.ArgumentParser(description="Lite vs Heavy pose benchmark")
    parser.add_argument("clips", nargs="+")
    parser.add_argument("--models", default="lite,heavy")
    parser.add_argument("--max-frames", type=int, default=None)
    args = parser.parse_args(argv)
    wanted = [name.strip() for name in args.models.split(",") if name.strip()]
    paths = {}
    if "lite" in wanted:
        paths["lite"] = _model_path(LITE_URL, "pose_landmarker_lite.task")
    if "heavy" in wanted:
        paths["heavy"] = _model_path(HEAVY_URL, "pose_landmarker_heavy.task")
    reports = []
    for clip in args.clips:
        for label, path in paths.items():
            reports.append(_run_clip(clip, path, label, max_frames=args.max_frames))
            print(json.dumps(reports[-1], indent=2))
    return reports


if __name__ == "__main__":
    main(sys.argv[1:])
