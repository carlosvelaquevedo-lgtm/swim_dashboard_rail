"""GoPro and phone ingestion, plus the tracking geometry the dashboard calls."""
import os
import subprocess
import tempfile
import unittest

import ingest
import video_preflight as pre


def _run(command):
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise AssertionError(result.stderr.decode(errors="replace")[-500:])
    return result


def _lavfi(path, size="160x90", rate=30, duration=1.0, pix_fmt="yuv420p", extra=None):
    command = [
        "ffmpeg", "-hide_banner", "-v", "error", "-y",
        "-f", "lavfi", "-i", f"testsrc2=size={size}:rate={rate}:duration={duration}",
        "-pix_fmt", pix_fmt, "-c:v", "libx264", "-preset", "ultrafast",
    ]
    if extra:
        command.extend(extra)
    command.append(path)
    _run(command)


class ProbeTests(unittest.TestCase):
    def test_skips_audio_and_cover_and_reads_the_real_stream(self):
        folder = tempfile.mkdtemp()
        video = os.path.join(folder, "video.mp4")
        cover = os.path.join(folder, "cover.jpg")
        multi = os.path.join(folder, "multi.mp4")
        try:
            _lavfi(video, duration=0.5)
            _run([
                "ffmpeg", "-hide_banner", "-v", "error", "-y",
                "-f", "lavfi", "-i", "color=c=red:s=32x32:d=0.1",
                "-frames:v", "1", cover,
            ])
            _run([
                "ffmpeg", "-hide_banner", "-v", "error", "-y",
                "-f", "lavfi", "-i", "anullsrc=r=8000:cl=mono",
                "-i", cover, "-i", video,
                "-map", "0:a", "-map", "1:v", "-map", "2:v",
                "-c:a", "aac", "-c:v", "copy",
                "-disposition:v:0", "attached_pic",
                "-metadata:s:v:1", "encoder=GoPro AVC",
                "-t", "0.5",
                multi,
            ])
            meta = ingest.probe_video_metadata(multi)
            self.assertIsNotNone(meta)
            self.assertNotEqual(meta["video_stream_index"], 0)
            self.assertEqual(meta["codec"], "h264")
            self.assertTrue(meta["is_gopro"])
            self.assertGreater(meta["duration"], 0)
            out, ok, message = ingest.normalize_video_to_cfr(
                multi, video_stream_index=meta["video_stream_index"],
            )
            self.assertTrue(ok, message)
            normalized = ingest.probe_video_metadata(out)
            self.assertEqual(normalized["codec"], "h264")
            self.assertEqual(normalized["pix_fmt"], "yuv420p")
            os.unlink(out)
        finally:
            for path in (video, cover, multi):
                if os.path.exists(path):
                    os.unlink(path)
            os.rmdir(folder)

    def test_audio_only_has_no_video_stream(self):
        path = tempfile.NamedTemporaryFile(delete=False, suffix=".m4a").name
        try:
            _run([
                "ffmpeg", "-hide_banner", "-v", "error", "-y",
                "-f", "lavfi", "-i", "anullsrc=r=8000:cl=mono",
                "-t", "0.3", "-c:a", "aac", path,
            ])
            self.assertIsNone(ingest.probe_video_metadata(path))
            out, ok, message = ingest.normalize_video_to_cfr(path)
            self.assertFalse(ok)
            self.assertEqual(out, path)
            self.assertIn("no video", message)
        finally:
            os.unlink(path)

    def test_rotation_tag_and_matrix_swap_display_size(self):
        # This ffmpeg build drops a rotate tag while muxing, so the reader is
        # checked against the stream dictionaries ffprobe actually returns.
        self.assertEqual(ingest._rotation_degrees({"tags": {"rotate": "90"}}), 90)
        self.assertEqual(ingest._rotation_degrees({"tags": {"rotate": "270"}}), 270)
        self.assertEqual(
            ingest._rotation_degrees({"side_data_list": [{"rotation": -90}]}),
            90,
        )
        self.assertEqual(ingest.display_dimensions(1920, 1080, 90), (1080, 1920))
        self.assertEqual(ingest.display_dimensions(1920, 1080, 180), (1920, 1080))
        self.assertEqual(ingest.display_dimensions(1920, 1080, 0), (1920, 1080))
        self.assertTrue(ingest._is_gopro(
            {"streams": [{"codec_tag_string": "gpmd"}]},
            {"tags": {}},
        ))
        self.assertFalse(ingest._is_gopro(
            {"streams": [{"codec_tag_string": "tmcd"}]},
            {"tags": {"encoder": "Lavc"}},
        ))


class NormalizeTests(unittest.TestCase):
    def _assert_cfr(self, path, frames_at_least=1, portrait=None):
        meta = ingest.probe_video_metadata(path)
        self.assertEqual(meta["codec"], "h264")
        self.assertEqual(meta["pix_fmt"], "yuv420p")
        self.assertEqual(meta["rotation"], 0)
        self.assertAlmostEqual(meta["src_fps"], 30.0, delta=0.1)
        self.assertGreaterEqual(meta["nb_frames"], frames_at_least)
        if portrait is True:
            self.assertGreater(meta["height"], meta["width"])
        if portrait is False:
            self.assertGreaterEqual(meta["width"], meta["height"])
        os.unlink(path)

    def test_ten_bit_hevc_and_full_range_and_high_fps(self):
        hevc = tempfile.NamedTemporaryFile(delete=False, suffix=".mov").name
        full = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
        fast = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
        try:
            _run([
                "ffmpeg", "-hide_banner", "-v", "error", "-y",
                "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=30:duration=0.4",
                "-pix_fmt", "yuv420p10le", "-c:v", "libx265", "-preset", "ultrafast",
                hevc,
            ])
            out, ok, _message = ingest.normalize_video_to_cfr(hevc)
            self.assertTrue(ok, _message)
            self._assert_cfr(out)

            _run([
                "ffmpeg", "-hide_banner", "-v", "error", "-y",
                "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=30:duration=0.4",
                "-pix_fmt", "yuvj420p", "-c:v", "mpeg4", full,
            ])
            out, ok, _message = ingest.normalize_video_to_cfr(full)
            self.assertTrue(ok, _message)
            self._assert_cfr(out)

            _lavfi(fast, rate=120, duration=0.5)
            out, ok, _message = ingest.normalize_video_to_cfr(fast)
            self.assertTrue(ok, _message)
            meta = ingest.probe_video_metadata(out)
            self.assertAlmostEqual(meta["src_fps"], 30.0, delta=0.1)
            self.assertLessEqual(meta["nb_frames"], 20)
            os.unlink(out)
        finally:
            for path in (hevc, full, fast):
                if os.path.exists(path):
                    os.unlink(path)

    def test_rotation_slowmo_and_input_seek(self):
        path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
        try:
            _lavfi(path, size="320x180", rate=30, duration=4.0)
            out, ok, message = ingest.normalize_video_to_cfr(path, orientation="rot90cw")
            self.assertTrue(ok, message)
            self._assert_cfr(out, portrait=True)

            out, ok, message = ingest.normalize_video_to_cfr(
                path, playback_speed=0.25, duration_s=4.0,
            )
            self.assertTrue(ok, message)
            meta = ingest.probe_video_metadata(out)
            # 4s of a 0.25x export, sped back to 1x, is 1s at 30fps.
            self.assertAlmostEqual(meta["nb_frames"], 30, delta=2)
            os.unlink(out)

            out, ok, message = ingest.normalize_video_to_cfr(
                path, start_s=1.0, duration_s=1.0, orientation="flip180",
            )
            self.assertTrue(ok, message)
            meta = ingest.probe_video_metadata(out)
            self.assertAlmostEqual(meta["nb_frames"], 30, delta=2)
            self.assertEqual(meta["rotation"], 0)
            os.unlink(out)
        finally:
            if os.path.exists(path):
                os.unlink(path)


class TrackingGeometryTests(unittest.TestCase):
    def test_coast_holds_eleven_misses_and_clears_on_the_twelfth(self):
        center, size, misses = (10.0, 20.0), 100.0, 0
        for _ in range(11):
            center, size, misses = pre.coast_track(center, size, misses)
            self.assertEqual(center, (10.0, 20.0))
            self.assertGreater(size, 100.0)
        center, size, misses = pre.coast_track(center, size, misses)
        self.assertIsNone(center)
        self.assertIsNone(size)
        self.assertEqual(misses, 0)

    def test_tiles_overlap_and_timestamps_increase(self):
        boxes = pre.tile_boxes(1920, 1080)
        self.assertEqual(len(boxes), 3)
        for x0, y0, x1, y1 in boxes:
            self.assertEqual(y0, 0)
            self.assertEqual(y1, 1080)
            self.assertGreaterEqual(x0, 0)
            self.assertLessEqual(x1, 1920)
            self.assertAlmostEqual((x1 - x0) / 1920, 0.60, delta=0.01)
        self.assertLess(boxes[0][0], boxes[1][0])
        self.assertLess(boxes[1][0], boxes[2][0])
        self.assertTrue(pre.should_probe_tiles(3))
        self.assertFalse(pre.should_probe_tiles(1))
        last = 33
        seen = []
        for _box in boxes:
            last = pre.next_timestamp(last)
            seen.append(last)
        self.assertEqual(seen, [34, 35, 36])

    def test_rejected_clip_does_not_earn_a_credit(self):
        self.assertFalse(pre.should_persist_report(False, True))
        self.assertFalse(pre.should_persist_report(True, False))
        self.assertFalse(pre.should_persist_report(True, True, framing_blocked=True))
        self.assertTrue(pre.should_persist_report(True, True))

    def test_write_is_gated_by_the_persist_helper(self):
        def attempt(normalized_ok, coverage_ok, framing_blocked=False):
            written = []
            if pre.should_persist_report(
                normalized_ok, coverage_ok, framing_blocked=framing_blocked
            ):
                written.append("meta")
            return written

        self.assertFalse(pre.should_persist_report(False, True))
        self.assertEqual(attempt(False, True), [])
        self.assertFalse(pre.should_persist_report(True, False))
        self.assertEqual(attempt(True, False), [])
        self.assertFalse(pre.should_persist_report(True, True, framing_blocked=True))
        self.assertEqual(attempt(True, True, True), [])
        self.assertEqual(attempt(True, True, False), ["meta"])

        dashboard = os.path.join(os.path.dirname(__file__), "..", "pages", "2_Dashboard.py")
        with open(dashboard, encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn(
            "should_persist_report(normalization_ok, coverage_ok, framing_blocked=framing_blocked)",
            source,
        )
        self.assertNotIn("should_persist_report(True, True, framing_blocked=False)", source)

    def test_framing_verdict_uses_the_largest_sample(self):
        self.assertEqual(pre.framing_verdict([None, None, None]), "skipped")
        self.assertEqual(pre.framing_verdict([0.0, 0.0]), "no_swimmer")
        self.assertEqual(pre.framing_verdict([0.05, 0.10]), "too_small")
        self.assertEqual(pre.framing_verdict([0.05, 0.40]), "ok")
        self.assertEqual(pre.sample_times(2.0, 8.0), (4.0, 6.0, 8.0))


if __name__ == "__main__":
    unittest.main()
