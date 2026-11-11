"""Modal L4 entry for the 3D lift.

Importing this module does not import torch, transformers, or modal. Those
load only when the GPU class is defined (`modal run`) or a clip is lifted.
Nothing here is imported by the Railway app. The image bakes both ViTPose
sizes; which one ships is decided by running both on the two test clips.

This file has not been executed on a GPU or on a swim clip.
"""
import hmac
import os

from modal_3d.canonical import (
    align_image_joints,
    coco17_to_h36m,
    flip_h36m,
    smooth_joints,
    to_pool,
)
from modal_3d.gates import evaluate
from modal_3d.retarget import build_stroke

LITE_CONFIG = dict(
    dim_in=3, dim_out=3, dim_feat=256, dim_rep=512, depth=5,
    num_heads=8, mlp_ratio=4, num_joints=17, maxlen=243, att_fuse=True,
)
VITPOSE_IDS = {
    "base": "usyd-community/vitpose-plus-base",
    "huge": "usyd-community/vitpose-plus-huge",
}
RTDETR_ID = "PekingU/rtdetr_r50vd_coco_o365"
MOTIONBERT_FILE = "checkpoint/pose3d/FT_MB_lite_MB_ft_h36m_global_lite/best_epoch.bin"
MODEL_ROOT = "/models"


def h36m_confidence(coco_scores):
    """Per-joint confidence in H36M order, from COCO scores."""
    import numpy as np
    scores = np.asarray(coco_scores, dtype=float)
    h36m = coco17_to_h36m(scores[..., None])[..., 0]
    return h36m


def assemble_from_lift(coco_xy, coco_scores, canonical_3d, fps):
    """Turn a lifter's upright 3D into pool joints, gates, and a stroke file.

    canonical_3d is (T, 17, 3) in the upright image frame the lifter was fed
    (y down). Gates see the raw pool joints. The rig is scaled only after that.
    A failed gate returns stroke=None so the caller does not write meta.json.
    """
    h36m_2d = coco17_to_h36m(coco_xy)
    _aligned, theta, center = align_image_joints(h36m_2d)
    raw_pool = to_pool(canonical_3d, theta, center)
    gates = evaluate(raw_pool, coco_scores, fps, coco_xy=coco_xy)
    if not gates["passed"]:
        return None, gates
    smoothed = smooth_joints(raw_pool, h36m_confidence(coco_scores))
    return build_stroke(smoothed, fps), gates


def _normalize_2d(points):
    """MotionBERT's crop_scale: valid x,y to [-1, 1], confidence kept."""
    import numpy as np
    out = np.array(points, dtype=np.float32, copy=True)
    valid = out[..., 2] > 0
    coords = out[valid][:, :2]
    if len(coords) < 4:
        return out
    span = max(coords[:, 0].max() - coords[:, 0].min(), coords[:, 1].max() - coords[:, 1].min())
    if span <= 0:
        return out
    origin = np.array([
        (coords[:, 0].min() + coords[:, 0].max() - span) / 2,
        (coords[:, 1].min() + coords[:, 1].max() - span) / 2,
    ])
    out[..., :2] = (out[..., :2] - origin) / span
    out[..., :2] = (out[..., :2] - 0.5) * 2
    return np.clip(out, -1, 1)


def _windows(total, length=243):
    if total <= length:
        return [(0, total)]
    starts = list(range(0, total - length + 1, length))
    if starts[-1] != total - length:
        starts.append(total - length)
    return [(start, start + length) for start in starts]


def load_motionbert(checkpoint_path, device="cpu"):
    """Build the Lite architecture and load weights with strict=True."""
    import torch
    from modal_3d.motionbert_arch import DSTformer

    model = DSTformer(**LITE_CONFIG)
    blob = torch.load(checkpoint_path, map_location=device)
    state = blob
    if isinstance(blob, dict):
        for key in ("model_pos", "model", "state_dict"):
            if key in blob and isinstance(blob[key], dict):
                state = blob[key]
                break
    cleaned = {}
    for key, value in state.items():
        cleaned[key.replace("module.", "")] = value
    model.load_state_dict(cleaned, strict=True)
    model.to(device)
    model.eval()
    return model


def _define_modal():
    """Build the Modal app. Called only by `modal run`, which imports modal."""
    import modal

    app = modal.App("swimform-3d")
    image = (
        modal.Image.debian_slim(python_version="3.11")
        .apt_install("ffmpeg", "libgl1", "libglib2.0-0")
        .pip_install(
            "torch",
            "transformers",
            "huggingface_hub",
            "opencv-python-headless",
            "numpy",
            "fastapi[standard]",
        )
        .run_function(download_models, timeout=60 * 30)
        .add_local_python_source("modal_3d")
    )

    @app.cls(
        image=image,
        gpu="L4",
        timeout=180,
        scaledown_window=15,
        enable_memory_snapshot=True,
        experimental_options={"enable_gpu_snapshot": True},
        secrets=[modal.Secret.from_name("swimform-3d")],
    )
    class Lifter:
        @modal.enter()
        def load(self):
            self.device = "cuda"
            self._load_models()

        def _load_models(self):
            import torch
            from transformers import AutoImageProcessor, AutoModelForObjectDetection, AutoProcessor, VitPoseForPoseEstimation

            self.torch = torch
            self.detector_proc = AutoImageProcessor.from_pretrained(f"{MODEL_ROOT}/rtdetr")
            self.detector = AutoModelForObjectDetection.from_pretrained(f"{MODEL_ROOT}/rtdetr").to(self.device).eval()
            self.pose = {}
            self.pose_proc = {}
            for name in VITPOSE_IDS:
                self.pose_proc[name] = AutoProcessor.from_pretrained(f"{MODEL_ROOT}/vitpose-{name}")
                self.pose[name] = VitPoseForPoseEstimation.from_pretrained(
                    f"{MODEL_ROOT}/vitpose-{name}"
                ).to(self.device).eval()
            self.lifter = load_motionbert(f"{MODEL_ROOT}/motionbert/{MOTIONBERT_FILE}", self.device)

        @modal.method()
        def lift_path(self, video_path, model_size="base"):
            return lift_video(self, video_path, model_size)

        @modal.fastapi_endpoint(method="POST")
        async def lift3d(self, request: "object"):
            return await _http_lift(self, request)

    @app.local_entrypoint()
    def main(video: str, out: str = "stroke3d.json", model_size: str = "base"):
        import json
        result = Lifter().lift_path.remote(video, model_size)
        with open(out, "w", encoding="utf-8") as handle:
            json.dump(result, handle)
        print(out, "passed" if result.get("gates", {}).get("passed") else "failed")

    return app


def download_models():
    """Image-build step. Both ViTPose sizes, so the clip test can compare them."""
    from huggingface_hub import snapshot_download

    snapshot_download(RTDETR_ID, local_dir=f"{MODEL_ROOT}/rtdetr")
    for name, repo in VITPOSE_IDS.items():
        snapshot_download(repo, local_dir=f"{MODEL_ROOT}/vitpose-{name}")
    snapshot_download(
        "walterzhu/MotionBERT",
        local_dir=f"{MODEL_ROOT}/motionbert",
        allow_patterns=[MOTIONBERT_FILE, "LICENSE"],
    )


def lift_video(lifter, video_path, model_size):
    """Read a normalized mp4, detect, pose, lift, gate. Returns JSON-ready dict."""
    import cv2
    from modal_3d.tracker import (
        ROTATIONS,
        SCORE_MIN,
        BoxTrack,
        fill_gaps,
        pad_box,
        should_detect,
        tiles_2x2,
        unrotate_box,
    )

    if model_size not in VITPOSE_IDS:
        raise ValueError("model_size must be 'base' or 'huge'")
    capture = cv2.VideoCapture(video_path)
    frames = []
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        frames.append(frame)
    fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    capture.release()
    if not frames:
        return {"ok": False, "error": "no frames", "gates": {"passed": False}}
    height, width = frames[0].shape[:2]
    track = BoxTrack()
    boxes = [None] * len(frames)
    last_score = None
    for index, frame in enumerate(frames):
        if not should_detect(index, last_score):
            continue
        detections = _detect_people(lifter, frame, width, height)
        box = track.update(detections)
        boxes[index] = box
        last_score = track.score
    boxes = fill_gaps(boxes)
    crops = []
    crop_boxes = []
    for frame, box in zip(frames, boxes):
        if box is None:
            crops.append(None)
            crop_boxes.append(None)
            continue
        padded = pad_box(box, width, height)
        crop_boxes.append(padded)
        x0, y0, x1, y1 = [int(round(v)) for v in padded]
        crops.append(frame[max(0, y0):max(0, y1), max(0, x0):max(0, x1)])
    coco_xy, coco_scores = _vitpose(lifter, frames, crop_boxes, model_size)
    canonical = _motionbert(lifter, coco_xy, coco_scores)
    stroke, gates = assemble_from_lift(coco_xy, coco_scores, canonical, fps)
    return {"ok": bool(gates["passed"]), "gates": gates, "stroke": stroke, "model_size": model_size}


def _detect_people(lifter, frame, width, height):
    """Three rotations, then 2x2 tiles when the best score is under 0.45."""
    import numpy as np
    found = []
    for degrees in ROTATIONS:
        rotated = _rotate_image(frame, degrees)
        for box, score in _rtdetr_people(lifter, rotated):
            found.append((unrotate_box(box, width, height, degrees), score))
    if not found or max(score for _box, score in found) < SCORE_MIN:
        for tile in tiles_2x2(width, height):
            x0, y0, x1, y1 = tile
            crop = frame[y0:y1, x0:x1]
            for box, score in _rtdetr_people(lifter, crop):
                found.append((
                    (box[0] + x0, box[1] + y0, box[2] + x0, box[3] + y0),
                    score,
                ))
    return found


def _rotate_image(frame, degrees):
    import cv2
    if degrees == 0:
        return frame
    if degrees == 90:
        return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)


def _rtdetr_people(lifter, image):
    import torch
    torch = lifter.torch
    height, width = image.shape[:2]
    inputs = lifter.detector_proc(images=image[:, :, ::-1], return_tensors="pt")
    inputs = {key: value.to(lifter.device) for key, value in inputs.items()}
    with torch.no_grad():
        outputs = lifter.detector(**inputs)
    results = lifter.detector_proc.post_process_object_detection(
        outputs, target_sizes=[(height, width)], threshold=0.25,
    )[0]
    people = []
    for box, score, label in zip(results["boxes"], results["scores"], results["labels"]):
        if int(label) != 0:
            continue
        people.append((tuple(float(v) for v in box.tolist()), float(score)))
    return people


def _vitpose(lifter, frames, boxes, model_size):
    import numpy as np
    import torch
    total = len(frames)
    xy = np.zeros((total, 17, 2), dtype=np.float32)
    scores = np.zeros((total, 17), dtype=np.float32)
    batch = []
    indexes = []

    def flush():
        if not batch:
            return
        images = [frame[:, :, ::-1] for frame in batch]
        box_arg = [[list(box)] for box in indexes_boxes]
        proc = lifter.pose_proc[model_size]
        model = lifter.pose[model_size]
        inputs = proc(images=images, boxes=box_arg, return_tensors="pt")
        inputs = {key: value.to(lifter.device) if hasattr(value, "to") else value for key, value in inputs.items()}
        with torch.no_grad(), torch.autocast(lifter.device, dtype=torch.bfloat16):
            outputs = model(**inputs)
        poses = proc.post_process_pose_estimation(outputs, boxes=box_arg)
        for index, pose_list in zip(indexes, poses):
            if not pose_list:
                continue
            keypoints = pose_list[0]["keypoints"].detach().float().cpu().numpy()
            conf = pose_list[0]["scores"].detach().float().cpu().numpy()
            xy[index] = keypoints[:, :2]
            scores[index] = conf
        batch.clear()
        indexes.clear()
        indexes_boxes.clear()

    indexes_boxes = []
    for index, (frame, box) in enumerate(zip(frames, boxes)):
        if box is None:
            continue
        batch.append(frame)
        indexes.append(index)
        indexes_boxes.append(box)
        if len(batch) == 64:
            flush()
    flush()
    return xy, scores


def _motionbert(lifter, coco_xy, coco_scores):
    """Upright 2D in, canonical 3D out. Flip test-time augmentation is averaged."""
    import numpy as np
    import torch
    h36m = coco17_to_h36m(np.concatenate([coco_xy, coco_scores[..., None]], axis=-1))
    _aligned, theta, center = align_image_joints(h36m[..., :2])
    aligned = h36m.copy()
    aligned[..., :2] = _aligned
    total = len(aligned)
    output = np.zeros((total, 17, 3), dtype=np.float32)
    weight = np.zeros((total, 1, 1), dtype=np.float32)
    for start, stop in _windows(total):
        window = aligned[start:stop]
        if len(window) < 243:
            pad = np.repeat(window[-1:], 243 - len(window), axis=0)
            window = np.concatenate([window, pad], axis=0)
        else:
            window = window[:243]
        pred = _lift_window(lifter, window)
        length = min(stop - start, pred.shape[0])
        output[start:start + length] += pred[:length]
        weight[start:start + length] += 1
    weight[weight == 0] = 1
    return output / weight


def _lift_window(lifter, window):
    import numpy as np
    import torch
    normal = _normalize_2d(window)
    flipped = flip_h36m(normal)
    batch = np.stack([normal, flipped]).astype(np.float32)
    tensor = torch.from_numpy(batch).to(lifter.device)
    with torch.no_grad():
        pred = lifter.lifter(tensor).float().cpu().numpy()
    pred[1] = flip_h36m(pred[1])
    return ((pred[0] + pred[1]) * 0.5).astype(np.float32)


def lift_auth_status(authorization, expected):
    """401 when the bearer token is missing or wrong. None means the token matches."""
    if not expected or not isinstance(authorization, str):
        return 401
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        return 401
    token = authorization[len(prefix):]
    if not token:
        return 401
    try:
        matches = hmac.compare_digest(token, expected)
    except (TypeError, ValueError):
        return 401
    return None if matches else 401


def _unauthorized_response():
    body = {"ok": False, "error": "unauthorized"}
    try:
        from fastapi.responses import JSONResponse
    except ImportError:
        from starlette.responses import JSONResponse
    return JSONResponse(body, status_code=401)


async def _http_lift(lifter, request):
    import json
    import tempfile
    auth = request.headers.get("authorization", "")
    expected = os.environ.get("MODAL_3D_TOKEN", "")
    if lift_auth_status(auth, expected):
        return _unauthorized_response()
    payload = await request.json()
    import base64
    raw = base64.b64decode(payload.get("video_b64") or "")
    if not raw:
        return {"ok": False, "error": "empty video"}
    model_size = payload.get("model_size") or "base"
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    handle.write(raw)
    handle.close()
    try:
        return lift_video(lifter, handle.name, model_size)
    finally:
        try:
            os.unlink(handle.name)
        except OSError:
            pass


try:
    app = _define_modal()
except Exception:
    # Local tests and py_compile import this module with no Modal install.
    app = None
