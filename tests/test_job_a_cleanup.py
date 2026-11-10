"""Job A: duration probe cache and analysis cleanup order."""
import os
import subprocess
import tempfile
import unittest
from io import BytesIO

import ingest


class _Upload:
    def __init__(self, name, data):
        self.name = name
        self.size = len(data)
        self._buf = BytesIO(data)
        self.seeks = 0

    def seek(self, pos):
        self.seeks += 1
        self._buf.seek(pos)

    def read(self, n=-1):
        return self._buf.read(n)


class DurationProbeTests(unittest.TestCase):
    def test_probes_once_and_deletes_temp_file(self):
        calls = []

        def fake_probe(path, timeout=15):
            calls.append(path)
            self.assertTrue(os.path.exists(path))
            return 12.5

        orig = ingest.probe_duration_seconds
        ingest.probe_duration_seconds = fake_probe
        try:
            upload = _Upload("clip.mp4", b"video-bytes")
            cache = {}
            self.assertEqual(ingest.cached_duration(cache, upload, True), 12.5)
            self.assertEqual(ingest.cached_duration(cache, upload, True), 12.5)
        finally:
            ingest.probe_duration_seconds = orig

        self.assertEqual(len(calls), 1)
        self.assertFalse(os.path.exists(calls[0]))
        self.assertGreaterEqual(upload.seeks, 1)

    def test_timeout_or_failure_still_deletes_temp_file(self):
        seen = []

        def explode(path, timeout=15):
            seen.append(path)
            raise subprocess.TimeoutExpired(cmd="ffprobe", timeout=30)

        orig = ingest.probe_duration_seconds
        ingest.probe_duration_seconds = explode
        try:
            upload = _Upload("clip.mov", b"abcdef")
            with self.assertRaises(subprocess.TimeoutExpired):
                ingest.cached_duration({}, upload, True)
        finally:
            ingest.probe_duration_seconds = orig

        self.assertEqual(len(seen), 1)
        self.assertFalse(os.path.exists(seen[0]))

    def test_ffprobe_internal_timeout_returns_none_and_deletes(self):
        def hang(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="ffprobe", timeout=15)

        orig = subprocess.run
        subprocess.run = hang
        try:
            path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
            try:
                self.assertIsNone(ingest.probe_duration_seconds(path))
            finally:
                os.unlink(path)
        finally:
            subprocess.run = orig


class CleanupOrderTests(unittest.TestCase):
    def test_closes_before_unlink_when_stop_is_raised(self):
        order = []
        path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name

        class Cap:
            def release(self):
                order.append("cap")
                self.assert_file_still_there()

            def assert_file_still_there(self):
                if not os.path.exists(path):
                    order.append("unlinked-too-early")

        class Container:
            def __init__(self, label):
                self.label = label

            def close(self):
                order.append(self.label)
                if not os.path.exists(path):
                    order.append("unlinked-too-early")
                if self.label == "slowmo":
                    raise RuntimeError("already closed")

        class Analyzer:
            def close(self):
                order.append("analyzer")
                if not os.path.exists(path):
                    order.append("unlinked-too-early")

        class Stop(BaseException):
            pass

        try:
            try:
                raise Stop()
            finally:
                ingest.release_analysis_resources(
                    cap=Cap(),
                    av_container=Container("av"),
                    slowmo_container=Container("slowmo"),
                    writer=None,
                    analyzer=Analyzer(),
                    paths=(path,),
                )
        except Stop:
            stopped = True
        else:
            stopped = False

        self.assertTrue(stopped)
        self.assertEqual(order, ["cap", "av", "slowmo", "analyzer"])
        self.assertNotIn("unlinked-too-early", order)
        self.assertFalse(os.path.exists(path))

    def test_slowmo_only_for_coach(self):
        self.assertTrue(ingest.encode_slowmo("coach"))
        self.assertFalse(ingest.encode_slowmo("swimmer"))


if __name__ == "__main__":
    unittest.main()
