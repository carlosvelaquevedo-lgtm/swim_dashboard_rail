"""Turn pool-space H36M joints into the pose object applyPose already takes.

Bone lengths are the viewer's (upper arm 0.30, forearm 0.27, thigh 0.44,
shin 0.43). That scaling happens here, after the gates have run on the raw
joints. COCO has no hand points, so the palm is a flat paddle and is not a
measurement. Roll and hand-entry crossover are estimates.
"""
import numpy as np

UPPER_ARM = 0.30
FOREARM = 0.27
THIGH = 0.44
SHIN = 0.43
SHOULDER_HALF = 0.18
HIP_HALF = 0.09
NECK_ANCHOR = np.array([0.33, -0.10, 0.0])
TORSO_LEN = 0.45

# H36M indexes.
R_HIP, R_KNEE, R_ANKLE = 1, 2, 3
L_HIP, L_KNEE, L_ANKLE = 4, 5, 6
L_SHOULDER, L_ELBOW, L_WRIST = 11, 12, 13
R_SHOULDER, R_ELBOW, R_WRIST = 14, 15, 16


def _unit(vector, fallback=None):
    vector = np.asarray(vector, dtype=float)
    length = float(np.linalg.norm(vector))
    if length < 1e-8:
        return np.array(fallback if fallback is not None else [1.0, 0.0, 0.0], dtype=float)
    return vector / length


def _vec(vector):
    return {"x": float(vector[0]), "y": float(vector[1]), "z": float(vector[2])}


def yaw_to_plus_x(joints):
    """Rotate around vertical so the average spine points along +X."""
    joints = np.asarray(joints, dtype=float)
    direction = (joints[:, 8, :] - joints[:, 0, :]).mean(axis=0)
    yaw = np.arctan2(direction[2], direction[0])
    c, s = np.cos(-yaw), np.sin(-yaw)
    out = joints.copy()
    x, z = joints[..., 0], joints[..., 2]
    out[..., 0] = c * x + s * z
    out[..., 2] = -s * x + c * z
    return out


def _frame_axes(joints):
    pelvis = joints[0]
    thorax = joints[8]
    forward = _unit(thorax - pelvis)
    up = np.array([0.0, 1.0, 0.0])
    dorsal0 = up - forward * np.dot(up, forward)
    dorsal0 = _unit(dorsal0, fallback=[0.0, 0.0, 1.0])
    right0 = _unit(np.cross(forward, dorsal0), fallback=[0.0, 0.0, 1.0])
    return forward, right0, dorsal0


def _roll(joints, forward, right0, dorsal0, positive, negative):
    line = joints[positive] - joints[negative]
    line = line - forward * np.dot(line, forward)
    line = _unit(line, fallback=right0)
    return float(np.arctan2(np.dot(line, dorsal0), np.dot(line, right0)))


def _frame_basis(right0, dorsal0, roll):
    right = right0 * np.cos(roll) + dorsal0 * np.sin(roll)
    dorsal = dorsal0 * np.cos(roll) - right0 * np.sin(roll)
    return {"right": _vec(right), "dorsal": _vec(dorsal)}, right, dorsal


def _arm(joints, start, shoulder, elbow, wrist):
    upper = _unit(joints[elbow] - joints[shoulder])
    fore = _unit(joints[wrist] - joints[elbow])
    mid = start + upper * UPPER_ARM
    end = mid + fore * FOREARM
    axis = _unit(end - start)
    pole = (mid - start) - axis * np.dot(mid - start, axis)
    pole = _unit(pole, fallback=[0.0, 1.0, 0.0])
    return {
        "S": _vec(start),
        "E": _vec(mid),
        "W": _vec(end),
        "pole": _vec(pole),
        "wBack": 0.0,
        "wRelax": 0.0,
        "wDown": 1.0,
    }


def _leg(joints, hip, knee, ankle):
    return {
        "thigh": _vec(_unit(joints[knee] - joints[hip])),
        "shin": _vec(_unit(joints[ankle] - joints[knee])),
    }


def _angle(a, b, c):
    u = np.asarray(a) - np.asarray(b)
    v = np.asarray(c) - np.asarray(b)
    denom = float(np.linalg.norm(u) * np.linalg.norm(v))
    if denom < 1e-8:
        return 0.0
    return float(np.degrees(np.arccos(np.clip(np.dot(u, v) / denom, -1.0, 1.0))))


def pose_from_joints(joints):
    """One applyPose pose. Vectors are {x, y, z}. Angles are radians."""
    joints = np.asarray(joints, dtype=float)
    forward, right0, dorsal0 = _frame_axes(joints)
    roll = _roll(joints, forward, right0, dorsal0, R_SHOULDER, L_SHOULDER)
    hip_roll = _roll(joints, forward, right0, dorsal0, R_HIP, L_HIP)
    sh_frame, sh_right, _sh_dorsal = _frame_basis(right0, dorsal0, roll)
    hip_frame, _hip_right, _hip_dorsal = _frame_basis(right0, dorsal0, hip_roll)
    neck = NECK_ANCHOR.copy()
    pelvis = neck - forward * TORSO_LEN
    return {
        "pelvis": _vec(pelvis),
        "neck": _vec(neck),
        "a": _vec(forward),
        "shF": sh_frame,
        "hipF": hip_frame,
        "headRoll": roll,
        "roll": roll,
        "hipRoll": hip_roll,
        "arms": {
            "R": _arm(joints, neck + sh_right * SHOULDER_HALF, R_SHOULDER, R_ELBOW, R_WRIST),
            "L": _arm(joints, neck - sh_right * SHOULDER_HALF, L_SHOULDER, L_ELBOW, L_WRIST),
        },
        "legs": {
            "R": _leg(joints, R_HIP, R_KNEE, R_ANKLE),
            "L": _leg(joints, L_HIP, L_KNEE, L_ANKLE),
        },
    }


def _summary(frames, joints):
    rolls = []
    catch_angle = None
    catch_depth = None
    entry_z = None
    for pose, frame in zip(frames, joints):
        rolls.append(pose["roll"])
        wrist = frame[R_WRIST]
        shoulder = frame[R_SHOULDER]
        depth = shoulder[1] - wrist[1]
        if catch_depth is None or depth > catch_depth:
            catch_depth = depth
            arm = pose["arms"]["R"]
            catch_angle = _angle(
                [arm["S"]["x"], arm["S"]["y"], arm["S"]["z"]],
                [arm["E"]["x"], arm["E"]["y"], arm["E"]["z"]],
                [arm["W"]["x"], arm["W"]["y"], arm["W"]["z"]],
            )
        if entry_z is None or wrist[1] > entry_z[0]:
            entry_z = (wrist[1], wrist[2] - frame[8][2])
    rolls = np.asarray(rolls) if rolls else np.zeros(1)
    return {
        "elbow_catch_deg": catch_angle,
        "roll_right_deg": float(np.degrees(rolls.max())),
        "roll_left_deg": float(np.degrees(-rolls.min())),
        "entry_z_m": None if entry_z is None else float(entry_z[1]),
        "labeled_as": "estimate",
    }


def build_stroke(joints, fps):
    """stroke3d.json contents. joints are (T, 17, 3) in pool space."""
    joints = yaw_to_plus_x(np.asarray(joints, dtype=float))
    frames = [pose_from_joints(frame) for frame in joints]
    return {
        "fps": float(fps),
        "duration_s": (len(frames) / float(fps)) if fps else 0.0,
        "coordinates": "+X swim, +Y up, +Z swimmer right",
        "bone_lengths_m": {
            "upper_arm": UPPER_ARM,
            "forearm": FOREARM,
            "thigh": THIGH,
            "shin": SHIN,
        },
        "estimates": ["roll", "hand_entry_crossover"],
        "you": _summary(frames, joints),
        "frames": frames,
    }
