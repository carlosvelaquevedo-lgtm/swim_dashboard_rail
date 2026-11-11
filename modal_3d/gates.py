"""Three checks on the raw 3D joints, before they are scaled to the X Bot rig.

Passing means the output is consistent. It does not mean the depth is right.
Roll and hand-entry crossover stay estimates until a side camera and a head-on
camera of the same swim are compared.
"""
import numpy as np

# COCO-17 indexes for the coverage check. The lifter's scores are still COCO.
TORSO = (5, 6, 11, 12)
ARM_L = (5, 7, 9)
ARM_R = (6, 8, 10)

# H36M-17 bones. Lengths are measured on the unscaled lifter output.
BONES = {
    "torso": (8, 0),
    "upper_arm_l": (12, 11),
    "upper_arm_r": (15, 14),
    "forearm_l": (13, 12),
    "forearm_r": (16, 15),
    "thigh_l": (5, 4),
    "thigh_r": (2, 1),
}
WRISTS = (13, 16)
ARM_PAIRS = (("upper_arm_l", "forearm_l"), ("upper_arm_r", "forearm_r"))

COVERAGE_MIN = 0.90
TORSO_CONF_MIN = 0.40
ARM_CONF_MIN = 0.35
BONE_CV_MAX = 0.10
ARM_LENGTH_M = 0.57
WRIST_PEAK_MAX = 6.5
WRIST_OUTLIER = 7.0
WRIST_OUTLIER_FRACTION = 0.02


def _detected_mask(scores):
    scores = np.asarray(scores, dtype=float)
    torso = scores[..., list(TORSO)].mean(axis=-1)
    # Any one shoulder, elbow, or wrist is enough. A whole arm is not required.
    arm = scores[..., list(ARM_L + ARM_R)].max(axis=-1)
    return (torso >= TORSO_CONF_MIN) & (arm >= ARM_CONF_MIN)


def _bone_lengths(joints):
    joints = np.asarray(joints, dtype=float)
    lengths = {}
    for name, (child, parent) in BONES.items():
        lengths[name] = np.linalg.norm(joints[:, child, :] - joints[:, parent, :], axis=-1)
    return lengths


def _cv(values):
    values = np.asarray(values, dtype=float)
    if values.size < 2:
        return None
    mean = float(np.mean(values))
    if mean <= 1e-8:
        return None
    return float(np.std(values) / mean)


def evaluate(joints_h36m, coco_scores, fps, coco_xy=None):
    """Return a gates report. `passed` is true only when all three pass.

    joints_h36m: (T, 17, 3) raw lifter joints, any scale.
    coco_scores: (T, 17) ViTPose confidence.
    coco_xy: optional (T, 17, 2) image points, y down, used only to label
    which arm was lower in the frame.
    """
    joints = np.asarray(joints_h36m, dtype=float)
    scores = np.asarray(coco_scores, dtype=float)
    fps = float(fps or 0.0)
    detected = _detected_mask(scores)
    coverage = float(detected.mean()) if detected.size else 0.0
    gate1 = bool(detected.size) and coverage >= COVERAGE_MIN

    submerged = recovery = None
    if coco_xy is not None and len(joints):
        xy = np.asarray(coco_xy, dtype=float)
        # The wrist lower on the screen (larger y) is the submerged one.
        left_lower = xy[:, 9, 1] >= xy[:, 10, 1]
        left_conf = scores[:, list(ARM_L)].mean(axis=-1)
        right_conf = scores[:, list(ARM_R)].mean(axis=-1)
        submerged = float(np.where(left_lower, left_conf, right_conf).mean())
        recovery = float(np.where(left_lower, right_conf, left_conf).mean())

    lengths = _bone_lengths(joints)
    confident = detected if detected.any() else np.ones(len(joints), dtype=bool)
    bone_cv = {}
    gate2 = True
    for name, series in lengths.items():
        cv = _cv(series[confident])
        bone_cv[name] = cv
        if cv is None or cv > BONE_CV_MAX:
            gate2 = False

    arm_sum = []
    for upper, fore in ARM_PAIRS:
        arm_sum.append(lengths[upper][confident] + lengths[fore][confident])
    stacked = np.concatenate(arm_sum) if arm_sum and arm_sum[0].size else np.array([])
    mean_arm = float(stacked.mean()) if stacked.size else 0.0
    scale = (ARM_LENGTH_M / mean_arm) if mean_arm > 1e-8 else 1.0
    scaled = joints * scale
    speeds = []
    if len(scaled) >= 2 and fps > 0:
        delta = np.linalg.norm(np.diff(scaled[:, list(WRISTS), :], axis=0), axis=-1) * fps
        speeds = delta
        peak = float(delta.max())
        outlier_frames = float(np.mean(delta.max(axis=-1) > WRIST_OUTLIER))
    else:
        peak = 0.0
        outlier_frames = 0.0
    gate3 = peak <= WRIST_PEAK_MAX and outlier_frames < WRIST_OUTLIER_FRACTION

    return {
        "passed": bool(gate1 and gate2 and gate3),
        "gate1_coverage": {
            "passed": gate1,
            "coverage": coverage,
            "required": COVERAGE_MIN,
            "detected_frames": int(detected.sum()),
            "frames": int(detected.size),
            "submerged_arm_conf": submerged,
            "recovery_arm_conf": recovery,
        },
        "gate2_bone_cv": {
            "passed": gate2,
            "cv": bone_cv,
            "max_allowed": BONE_CV_MAX,
        },
        "gate3_wrist_speed": {
            "passed": gate3,
            "peak_m_s": peak,
            "outlier_fraction": outlier_frames,
            "peak_max": WRIST_PEAK_MAX,
            "outlier_speed": WRIST_OUTLIER,
            "scale_to_meters": scale,
        },
        "depth_is_measured": False,
    }
