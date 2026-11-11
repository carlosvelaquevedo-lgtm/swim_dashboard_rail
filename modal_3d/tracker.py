"""Swimmer boxes for a horizontal, wide-angle clip.

The detector call is injected. Tests pass a fake one. RT-DETR itself is only
loaded inside modal_3d.app, on the GPU.
"""
import numpy as np

STRIDE = 5
SCORE_MIN = 0.45
COAST_FRAMES = 12
BOX_PAD = 1.35
ROTATIONS = (0, 90, -90)


def iou(a, b):
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    inter = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    area = max(0.0, ax1 - ax0) * max(0.0, ay1 - ay0) + max(0.0, bx1 - bx0) * max(0.0, by1 - by0) - inter
    if area <= 0:
        return 0.0
    return inter / area


def tiles_2x2(width, height, fraction=0.60):
    """Four overlapping tiles. Each is `fraction` of the frame on both sides."""
    width, height = int(width), int(height)
    tile_w = min(width, max(2, int(round(width * fraction))))
    tile_h = min(height, max(2, int(round(height * fraction))))
    xs = (0, max(0, width - tile_w))
    ys = (0, max(0, height - tile_h))
    boxes = []
    for y in ys:
        for x in xs:
            box = (x, y, x + tile_w, y + tile_h)
            if box not in boxes:
                boxes.append(box)
    return tuple(boxes)


def rotate_point(x, y, width, height, degrees):
    """Map an original-image point into an image rotated by degrees clockwise."""
    if degrees == 0:
        return x, y
    if degrees == 90:
        return height - 1 - y, x
    if degrees == -90 or degrees == 270:
        return y, width - 1 - x
    raise ValueError("rotation must be 0, 90, or -90")


def unrotate_point(x, y, width, height, degrees):
    """Inverse of rotate_point. width and height are the original size."""
    if degrees == 0:
        return x, y
    if degrees == 90:
        return y, height - 1 - x
    if degrees == -90 or degrees == 270:
        return width - 1 - y, x
    raise ValueError("rotation must be 0, 90, or -90")


def unrotate_box(box, width, height, degrees):
    """A box from a rotated image, back in the original image."""
    x0, y0, x1, y1 = box
    corners = (
        unrotate_point(x0, y0, width, height, degrees),
        unrotate_point(x1, y0, width, height, degrees),
        unrotate_point(x0, y1, width, height, degrees),
        unrotate_point(x1, y1, width, height, degrees),
    )
    xs = [point[0] for point in corners]
    ys = [point[1] for point in corners]
    return (min(xs), min(ys), max(xs), max(ys))


def pad_box(box, width, height, scale=BOX_PAD):
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    half_w = (x1 - x0) * scale / 2.0
    half_h = (y1 - y0) * scale / 2.0
    return (
        max(0.0, cx - half_w),
        max(0.0, cy - half_h),
        min(float(width), cx + half_w),
        min(float(height), cy + half_h),
    )


def should_detect(frame_index, last_score):
    """Keyframes, and any frame whose last box was a weak match."""
    if frame_index % STRIDE == 0:
        return True
    return last_score is None or last_score < SCORE_MIN


class BoxTrack:
    """Hold the last swimmer box through 12 missed frames."""

    def __init__(self):
        self.box = None
        self.score = None
        self.misses = 0

    def update(self, detections):
        """detections: list of (box, score) in the original image. Returns the box to use."""
        chosen = None
        if detections:
            if self.box is None:
                chosen = max(detections, key=lambda item: item[1])
            else:
                chosen = max(detections, key=lambda item: (iou(item[0], self.box), item[1]))
                if iou(chosen[0], self.box) < 0.05 and chosen[1] < SCORE_MIN:
                    chosen = None
        if chosen is not None and chosen[1] >= SCORE_MIN:
            self.box, self.score, self.misses = chosen[0], chosen[1], 0
            return self.box
        self.misses += 1
        if self.misses >= COAST_FRAMES or self.box is None:
            self.box, self.score, self.misses = None, None, 0
            return None
        return self.box


def fill_gaps(boxes, coast=COAST_FRAMES):
    """Linear fill between known boxes. A gap longer than `coast` stays empty."""
    known = [index for index, box in enumerate(boxes) if box is not None]
    filled = list(boxes)
    for left, right in zip(known, known[1:]):
        gap = right - left - 1
        if gap <= 0 or gap > coast:
            continue
        a = np.asarray(boxes[left], dtype=float)
        b = np.asarray(boxes[right], dtype=float)
        for step in range(1, gap + 1):
            if filled[left + step] is None:
                filled[left + step] = tuple((a + (b - a) * (step / (gap + 1))).tolist())
    return filled
