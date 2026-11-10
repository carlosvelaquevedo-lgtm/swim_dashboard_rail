"""Job C: torso stability, wrist jerk, and the +1 ms timestamp rule."""
import unittest

import pose_quality


class TimestampTests(unittest.TestCase):
    def test_first_timestamp_is_used_as_given(self):
        self.assertEqual(pose_quality.next_video_timestamp(None, 0), 0)

    def test_equal_or_earlier_timestamp_retries_one_millisecond_later(self):
        self.assertEqual(pose_quality.next_video_timestamp(33, 33), 34)
        self.assertEqual(pose_quality.next_video_timestamp(33, 10), 34)
        self.assertEqual(pose_quality.next_video_timestamp(33, 34), 34)


class MeasureTests(unittest.TestCase):
    def test_torso_cv_ignores_frames_missing_a_joint_and_is_zero_when_stable(self):
        stable = {
            "left_shoulder": (0, 0),
            "right_shoulder": (10, 0),
            "left_hip": (0, 40),
            "right_hip": (10, 40),
            "left_wrist": (0, 10),
            "right_wrist": None,
        }
        missing = dict(stable)
        missing["left_hip"] = None
        frames = [stable, missing, stable]
        lengths = pose_quality.torso_lengths(frames)
        self.assertEqual(len(lengths), 2)
        self.assertEqual(pose_quality.coefficient_of_variation(lengths), 0)

    def test_wrist_jerk_is_zero_for_constant_speed(self):
        frames = []
        for i in range(8):
            frames.append({
                "left_shoulder": (0, 0),
                "right_shoulder": (10, 0),
                "left_hip": (0, 40),
                "right_hip": (10, 40),
                "left_wrist": (i * 2.0, 0),
                "right_wrist": None,
            })
        jerk, count = pose_quality.wrist_jerk(frames, fps=10)
        self.assertGreater(count, 0)
        self.assertAlmostEqual(jerk, 0, places=6)

    def test_a_jumping_wrist_has_higher_jerk_than_a_smooth_one(self):
        def series(xs):
            return [{
                "left_shoulder": (0, 0), "right_shoulder": (4, 0),
                "left_hip": (0, 20), "right_hip": (4, 20),
                "left_wrist": (x, 0), "right_wrist": None,
            } for x in xs]
        smooth, _ = pose_quality.wrist_jerk(series([0, 1, 2, 3, 4, 5, 6, 7]), 10)
        jumpy, _ = pose_quality.wrist_jerk(series([0, 1, 9, 2, 8, 3, 7, 4]), 10)
        self.assertGreater(jumpy, smooth)


if __name__ == "__main__":
    unittest.main()
