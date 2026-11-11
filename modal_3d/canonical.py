"""COCO-17 to H36M-17, and the spine rotation that stands a swimmer upright.

Image axes are x right, y down. Pool axes are +X swim, +Y up, +Z the swimmer's
right. Rotating a horizontal swimmer upright before a lifter trained on standing
people is a hypothesis. These functions only guarantee the rotation round-trips.
"""
import numpy as np

# H36M-17 order used by MotionBERT (same as their halpe2h36m output).
PELVIS, THORAX = 0, 8
LEFT_H36M = [4, 5, 6, 11, 12, 13]
RIGHT_H36M = [1, 2, 3, 14, 15, 16]


def coco17_to_h36m(coco):
    """Map COCO-17 points to H36M-17.

    COCO has no neck, hip-center, or head-top. The hip center is the mid-hip,
    the thorax is the mid-shoulder, the spine is halfway between them, and the
    head is a short step past the nose away from the thorax. coco is (..., 17, C).
    """
    coco = np.asarray(coco, dtype=float)
    out = np.zeros(coco.shape[:-2] + (17, coco.shape[-1]), dtype=float)
    pelvis = (coco[..., 11, :] + coco[..., 12, :]) * 0.5
    thorax = (coco[..., 5, :] + coco[..., 6, :]) * 0.5
    nose = coco[..., 0, :]
    out[..., 0, :] = pelvis
    out[..., 1, :] = coco[..., 12, :]
    out[..., 2, :] = coco[..., 14, :]
    out[..., 3, :] = coco[..., 16, :]
    out[..., 4, :] = coco[..., 11, :]
    out[..., 5, :] = coco[..., 13, :]
    out[..., 6, :] = coco[..., 15, :]
    out[..., 7, :] = (pelvis + thorax) * 0.5
    out[..., 8, :] = thorax
    out[..., 9, :] = nose
    out[..., 10, :] = nose + (nose - thorax) * 0.3
    out[..., 11, :] = coco[..., 5, :]
    out[..., 12, :] = coco[..., 7, :]
    out[..., 13, :] = coco[..., 9, :]
    out[..., 14, :] = coco[..., 6, :]
    out[..., 15, :] = coco[..., 8, :]
    out[..., 16, :] = coco[..., 10, :]
    return out


def spine_theta(joints):
    """Angle of mid-hip -> mid-shoulder. 0 means the shoulder is straight up on screen."""
    joints = np.asarray(joints, dtype=float)
    delta = joints[..., THORAX, :2] - joints[..., PELVIS, :2]
    return np.arctan2(delta[..., 0], -delta[..., 1])


def _align_matrix(theta):
    """Maps a spine at `theta` onto straight up (image y decreasing)."""
    theta = np.asarray(theta, dtype=float)
    c = np.cos(theta)
    s = np.sin(theta)
    row0 = np.stack([c, s], axis=-1)
    row1 = np.stack([-s, c], axis=-1)
    return np.stack([row0, row1], axis=-2)


def _apply(xy, matrix):
    """xy is (T, J, 2) and matrix is (T, 2, 2). One matrix per frame, every joint."""
    return np.einsum("tij,tkj->tki", matrix, xy)


def align_image_joints(joints, center=None):
    """Rotate image-plane joints so the spine points up. z is left alone.

    Returns (aligned, theta, center). theta is one angle per frame.
    """
    joints = np.asarray(joints, dtype=float)
    flat = joints.reshape((-1,) + joints.shape[-2:])
    theta = spine_theta(flat)
    if center is None:
        center = flat[..., PELVIS, :2]
    else:
        center = np.asarray(center, dtype=float).reshape((-1, 2))
    matrix = _align_matrix(theta)
    xy = flat[..., :2] - center[:, None, :]
    aligned = flat.copy()
    aligned[..., :2] = _apply(xy, matrix) + center[:, None, :]
    return aligned.reshape(joints.shape), theta.reshape(joints.shape[:-2]), center.reshape(joints.shape[:-2] + (2,))


def invert_alignment(joints, theta, center):
    """Inverse of align_image_joints."""
    joints = np.asarray(joints, dtype=float)
    theta = np.asarray(theta, dtype=float).reshape((-1,))
    center = np.asarray(center, dtype=float).reshape((-1, 2))
    flat = joints.reshape((-1,) + joints.shape[-2:])
    matrix = np.swapaxes(_align_matrix(theta), -1, -2)
    xy = flat[..., :2] - center[:, None, :]
    restored = flat.copy()
    restored[..., :2] = _apply(xy, matrix) + center[:, None, :]
    return restored.reshape(joints.shape)


def image_to_pool(joints):
    """Side-camera image (y down) to pool axes, before any spine rotation."""
    joints = np.asarray(joints, dtype=float)
    pool = joints.copy()
    pool[..., 0] = joints[..., 0]
    pool[..., 1] = -joints[..., 1]
    if joints.shape[-1] > 2:
        pool[..., 2] = joints[..., 2]
    return pool


def pool_to_image(joints):
    """Inverse of image_to_pool."""
    joints = np.asarray(joints, dtype=float)
    image = joints.copy()
    image[..., 1] = -joints[..., 1]
    return image


def to_pool(canonical_3d, theta, center=None):
    """Undo the upright rotation and flip y so +Y is up.

    The rotation is around the lifted pelvis. The 2D pixel center is not in the
    lifter's coordinate system, so it is not used. `center` is accepted so older
    callers still run; the pelvis of canonical_3d is the pivot.
    """
    joints = np.asarray(canonical_3d, dtype=float)
    pivot = joints[..., PELVIS, :2]
    image = invert_alignment(joints, theta, pivot)
    return image_to_pool(image)


def smooth_joints(joints, confidence, radius=2):
    """Confidence-weighted moving average. A low score barely moves the joint."""
    joints = np.asarray(joints, dtype=float)
    conf = np.asarray(confidence, dtype=float)
    if conf.ndim == 1:
        conf = np.broadcast_to(conf[:, None], joints.shape[:2]).copy()
    out = np.empty_like(joints)
    total = joints.shape[0]
    for index in range(total):
        start = max(0, index - radius)
        stop = min(total, index + radius + 1)
        weight = np.clip(conf[start:stop], 1e-3, None)[..., None]
        out[index] = np.sum(joints[start:stop] * weight, axis=0) / np.sum(weight, axis=0)
    return out


def flip_h36m(data):
    """Left-right flip. X is the first channel. Flipping twice returns the input."""
    data = np.asarray(data, dtype=float)
    flipped = data.copy()
    flipped[..., 0] *= -1
    source = flipped[..., RIGHT_H36M + LEFT_H36M, :].copy()
    flipped[..., LEFT_H36M + RIGHT_H36M, :] = source
    return flipped
