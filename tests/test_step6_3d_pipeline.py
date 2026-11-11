"""Canonical spine rotation, the three gates, and the viewer pose export.

No GPU and no network. A real swim clip is still required before any 3D
readout is treated as a measurement.
"""
import unittest

import numpy as np

from modal_3d.canonical import (
    align_image_joints,
    coco17_to_h36m,
    flip_h36m,
    pool_to_image,
    spine_theta,
    to_pool,
)
from modal_3d.app import assemble_from_lift
from modal_3d.gates import _detected_mask, evaluate
from modal_3d.retarget import FOREARM, UPPER_ARM, build_stroke
from modal_3d.tracker import (
    BoxTrack,
    rotate_point,
    tiles_2x2,
    unrotate_box,
    unrotate_point,
)


def _standing():
    joints = np.zeros((17, 3), dtype=float)
    joints[0] = [0.0, 0.0, 0.0]
    joints[7] = [0.0, 0.25, 0.0]
    joints[8] = [0.0, 0.50, 0.0]
    joints[9] = [0.0, 0.65, 0.0]
    joints[10] = [0.0, 0.75, 0.0]
    joints[4] = [0.0, 0.0, -0.10]
    joints[1] = [0.0, 0.0, 0.10]
    joints[5] = [0.0, -0.45, -0.10]
    joints[2] = [0.0, -0.45, 0.10]
    joints[6] = [0.0, -0.90, -0.10]
    joints[3] = [0.0, -0.90, 0.10]
    joints[11] = [0.0, 0.50, -0.20]
    joints[14] = [0.0, 0.50, 0.20]
    joints[12] = [0.05, 0.20, -0.20]
    joints[15] = [0.05, 0.20, 0.20]
    joints[13] = [0.15, 0.00, -0.20]
    joints[16] = [0.15, 0.00, 0.20]
    return joints


def _rotate_z(joints, degrees):
    radians = np.deg2rad(degrees)
    c, s = np.cos(radians), np.sin(radians)
    out = np.array(joints, dtype=float, copy=True)
    x, y = out[..., 0].copy(), out[..., 1].copy()
    out[..., 0] = c * x - s * y
    out[..., 1] = s * x + c * y
    return out


def _horizontal(pitch_deg):
    """A swimmer whose spine lies in the sagittal plane, pitched from +X."""
    flat = _rotate_z(_standing(), -90)
    return _rotate_z(flat, pitch_deg)


def _roundtrip(pool):
    pool = np.asarray(pool, dtype=float)
    if pool.ndim == 2:
        pool = pool[None, ...]
    image = pool_to_image(pool)
    aligned, theta, center = align_image_joints(image)
    restored = to_pool(aligned, theta, center)
    return aligned, restored, pool


class CanonicalTests(unittest.TestCase):
    def test_horizontal_poses_stand_up_and_return(self):
        for pitch in (0.0, 180.0, -12.0):
            aligned, restored, pool = _roundtrip(_horizontal(pitch))
            self.assertLess(abs(float(spine_theta(aligned)[0])), 1e-5)
            # Upright on screen: the thorax is above the pelvis (smaller image y).
            self.assertLess(aligned[0, 8, 1], aligned[0, 0, 1])
            self.assertLess(np.max(np.abs(restored - pool)), 1e-5)

    def test_coco_midpoints_match_the_h36m_spine(self):
        pool = _horizontal(0.0)
        coco = np.zeros((1, 17, 2))
        coco[0, 0] = pool[9, :2]
        coco[0, 5] = pool[11, :2]
        coco[0, 6] = pool[14, :2]
        coco[0, 7] = pool[12, :2]
        coco[0, 8] = pool[15, :2]
        coco[0, 9] = pool[13, :2]
        coco[0, 10] = pool[16, :2]
        coco[0, 11] = pool[4, :2]
        coco[0, 12] = pool[1, :2]
        coco[0, 13] = pool[5, :2]
        coco[0, 14] = pool[2, :2]
        coco[0, 15] = pool[6, :2]
        coco[0, 16] = pool[3, :2]
        h36m = coco17_to_h36m(coco)
        self.assertLess(np.max(np.abs(h36m[0, 0] - (pool[4, :2] + pool[1, :2]) / 2)), 1e-6)
        self.assertLess(np.max(np.abs(h36m[0, 8] - (pool[11, :2] + pool[14, :2]) / 2)), 1e-6)

    def test_flip_twice_is_identity(self):
        pose = _horizontal(-12.0)[None, ...]
        self.assertLess(np.max(np.abs(flip_h36m(flip_h36m(pose)) - pose)), 1e-6)


class GateTests(unittest.TestCase):
    def _clip(self, frames=90):
        joints = np.repeat(_horizontal(0.0)[None, ...], frames, axis=0)
        joints[:, :, 0] += 0.02 * np.arange(frames)[:, None]
        scores = np.full((frames, 17), 0.95)
        return joints, scores

    def test_clean_freestyle_passes(self):
        joints, scores = self._clip()
        report = evaluate(joints, scores, fps=30.0, coco_xy=joints[..., :2])
        self.assertTrue(report["gate1_coverage"]["passed"])
        self.assertTrue(report["gate2_bone_cv"]["passed"])
        self.assertTrue(report["gate3_wrist_speed"]["passed"])
        self.assertTrue(report["passed"])
        self.assertFalse(report["depth_is_measured"])

    def test_one_wrist_counts_and_a_low_arm_does_not(self):
        # Hips keep the torso mean over 0.40 while every arm joint but one wrist is dim.
        scores = np.full((1, 17), 0.1)
        scores[0, 11] = 0.95
        scores[0, 12] = 0.95
        scores[0, 9] = 0.36
        self.assertTrue(bool(_detected_mask(scores)[0]))

        low = np.full((1, 17), 0.1)
        low[0, 11] = 0.95
        low[0, 12] = 0.95
        for index in (5, 6, 7, 8, 9, 10):
            low[0, index] = 0.34
        self.assertFalse(bool(_detected_mask(low)[0]))

    def test_occlusion_fails_coverage(self):
        joints, scores = self._clip()
        scores[:20, :] = 0.05
        report = evaluate(joints, scores, fps=30.0)
        self.assertFalse(report["gate1_coverage"]["passed"])
        self.assertFalse(report["passed"])

    def test_stretched_bone_fails(self):
        joints, scores = self._clip()
        direction = joints[:, 16, :] - joints[:, 15, :]
        joints[::2, 16, :] = joints[::2, 15, :] + direction[::2] * 2.0
        report = evaluate(joints, scores, fps=30.0)
        self.assertFalse(report["gate2_bone_cv"]["passed"])
        self.assertGreater(report["gate2_bone_cv"]["cv"]["forearm_r"], 0.10)

    def test_wrist_teleport_fails_speed(self):
        joints, scores = self._clip()
        joints[40:, :, :] += np.array([1.0, 0.0, 0.0])
        report = evaluate(joints, scores, fps=30.0)
        self.assertTrue(report["gate2_bone_cv"]["passed"])
        self.assertFalse(report["gate3_wrist_speed"]["passed"])
        self.assertGreater(report["gate3_wrist_speed"]["peak_m_s"], 6.5)

    def test_failed_gate_does_not_build_a_stroke(self):
        joints, scores = self._clip()
        scores[:] = 0.05
        image = pool_to_image(joints)
        aligned, theta, center = align_image_joints(image)
        stroke, report = assemble_from_lift(self._coco_from_h36m(image), scores, aligned, 30.0)
        self.assertIsNone(stroke)
        self.assertFalse(report["passed"])

    def test_passing_clip_exports_the_rig_pose(self):
        joints, scores = self._clip(frames=12)
        image = pool_to_image(joints)
        aligned, _theta, _center = align_image_joints(image)
        stroke, report = assemble_from_lift(self._coco_from_h36m(image), scores, aligned, 30.0)
        self.assertTrue(report["passed"])
        frame = stroke["frames"][0]
        for key in ("pelvis", "neck", "a", "shF", "hipF", "headRoll", "roll", "hipRoll", "arms", "legs"):
            self.assertIn(key, frame)
        arm = frame["arms"]["R"]
        self.assertAlmostEqual(_dist(arm["S"], arm["E"]), UPPER_ARM, places=5)
        self.assertAlmostEqual(_dist(arm["E"], arm["W"]), FOREARM, places=5)
        self.assertEqual(stroke["estimates"], ["roll", "hand_entry_crossover"])

    def _coco_from_h36m(self, image):
        coco = np.zeros(image.shape[:-2] + (17, 2))
        coco[..., 0, :] = image[..., 9, :2]
        coco[..., 5, :] = image[..., 11, :2]
        coco[..., 6, :] = image[..., 14, :2]
        coco[..., 7, :] = image[..., 12, :2]
        coco[..., 8, :] = image[..., 15, :2]
        coco[..., 9, :] = image[..., 13, :2]
        coco[..., 10, :] = image[..., 16, :2]
        coco[..., 11, :] = image[..., 4, :2]
        coco[..., 12, :] = image[..., 1, :2]
        coco[..., 13, :] = image[..., 5, :2]
        coco[..., 14, :] = image[..., 2, :2]
        coco[..., 15, :] = image[..., 6, :2]
        coco[..., 16, :] = image[..., 3, :2]
        return coco


def _dist(a, b):
    return float(np.linalg.norm([a["x"] - b["x"], a["y"] - b["y"], a["z"] - b["z"]]))


class TrackerTests(unittest.TestCase):
    def test_rotation_roundtrip_and_tiles(self):
        for degrees in (0, 90, -90):
            moved = rotate_point(10, 20, 1920, 1080, degrees)
            back = unrotate_point(moved[0], moved[1], 1920, 1080, degrees)
            self.assertAlmostEqual(back[0], 10, places=5)
            self.assertAlmostEqual(back[1], 20, places=5)
        box = unrotate_box((0, 0, 10, 20), 100, 80, 90)
        self.assertGreater(box[2], box[0])
        tiles = tiles_2x2(1920, 1080)
        self.assertEqual(len(tiles), 4)
        for x0, y0, x1, y1 in tiles:
            self.assertGreaterEqual(x0, 0)
            self.assertGreaterEqual(y0, 0)
            self.assertLessEqual(x1, 1920)
            self.assertLessEqual(y1, 1080)

    def test_coast_holds_eleven_and_clears_on_the_twelfth(self):
        track = BoxTrack()
        box = track.update([((0, 0, 10, 20), 0.9)])
        self.assertEqual(box, (0, 0, 10, 20))
        for _ in range(11):
            self.assertEqual(track.update([]), (0, 0, 10, 20))
        self.assertIsNone(track.update([]))


class LiftAuthTests(unittest.TestCase):
    def test_unauthorized_returns_401(self):
        import asyncio
        import os

        from modal_3d.app import _http_lift, lift_auth_status

        self.assertEqual(lift_auth_status(None, "secret"), 401)
        self.assertEqual(lift_auth_status("", "secret"), 401)
        self.assertEqual(lift_auth_status("Bearer wrong", "secret"), 401)
        self.assertEqual(lift_auth_status("secret", "secret"), 401)
        self.assertEqual(lift_auth_status("Bearer secret", ""), 401)
        self.assertIsNone(lift_auth_status("Bearer secret", "secret"))

        class Request:
            def __init__(self, auth):
                self.headers = {}
                if auth is not None:
                    self.headers["authorization"] = auth
                self.read_body = False

            async def json(self):
                self.read_body = True
                return {}

        previous = os.environ.get("MODAL_3D_TOKEN")
        os.environ["MODAL_3D_TOKEN"] = "secret"
        try:
            missing = Request(None)
            bad = Request("Bearer wrong")
            good = Request("Bearer secret")
            missing_result = asyncio.run(_http_lift(None, missing))
            bad_result = asyncio.run(_http_lift(None, bad))
            good_result = asyncio.run(_http_lift(None, good))
        finally:
            if previous is None:
                os.environ.pop("MODAL_3D_TOKEN", None)
            else:
                os.environ["MODAL_3D_TOKEN"] = previous

        self.assertEqual(missing_result.status_code, 401)
        self.assertEqual(bad_result.status_code, 401)
        self.assertFalse(missing.read_body)
        self.assertFalse(bad.read_body)
        self.assertTrue(good.read_body)
        self.assertEqual(good_result.get("error"), "empty video")
        app_path = os.path.join(os.path.dirname(__file__), "..", "modal_3d", "app.py")
        with open(app_path, encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn("hmac.compare_digest", source)


class StrokeFileTests(unittest.TestCase):
    def test_build_stroke_uses_the_viewer_schema(self):
        joints = np.repeat(_horizontal(0.0)[None, ...], 4, axis=0)
        stroke = build_stroke(joints, 30)
        self.assertEqual(len(stroke["frames"]), 4)
        self.assertIn("you", stroke)
        self.assertEqual(stroke["you"]["labeled_as"], "estimate")


if __name__ == "__main__":
    unittest.main()
