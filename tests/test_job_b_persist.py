"""Job B: session id, lock, meta.json credit, and the one-time report email."""
import json
import os
import tempfile
import time
import unittest
from types import SimpleNamespace

import payments
import results_store


class SessionTests(unittest.TestCase):
    def test_rejects_ids_that_are_not_checkout_sessions(self):
        for bad in ("", "abc", "../etc/passwd", "cs_live_../x", "cs_live_" + "a" * 9, "verified"):
            self.assertFalse(payments.valid_session_id(bad))
        self.assertTrue(payments.valid_session_id("cs_live_" + "a" * 20))
        self.assertTrue(payments.valid_session_id("cs_test_" + "B" * 24))

    def test_report_mode_prefers_metadata_then_amount(self):
        coach = SimpleNamespace(metadata={"report_mode": "coach"}, amount_total=99, customer_details=None)
        self.assertEqual(payments.report_mode_from_checkout(coach), "coach")
        by_amount = SimpleNamespace(metadata={}, amount_total=699, customer_details=SimpleNamespace(email="a@b.co"))
        self.assertEqual(payments.report_mode_from_checkout(by_amount), "coach")
        swimmer = SimpleNamespace(metadata={}, amount_total=99, customer_details={"email": "s@b.co"})
        self.assertEqual(payments.report_mode_from_checkout(swimmer), "swimmer")
        self.assertEqual(payments.email_from_checkout(by_amount), "a@b.co")
        self.assertEqual(payments.email_from_checkout(swimmer), "s@b.co")

    def test_invalid_id_is_not_a_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["SWIMFORM_RESULTS_DIR"] = tmp
            try:
                with self.assertRaises(ValueError):
                    results_store.session_dir("../etc/passwd")
            finally:
                os.environ.pop("SWIMFORM_RESULTS_DIR", None)


class LockAndCreditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["SWIMFORM_RESULTS_DIR"] = self.tmp.name
        self.sid = "cs_test_" + "c" * 16

    def tearDown(self):
        os.environ.pop("SWIMFORM_RESULTS_DIR", None)
        self.tmp.cleanup()

    def test_stale_lock_can_be_retried_and_meta_uses_the_credit(self):
        self.assertTrue(results_store.acquire_lock(self.sid, now=time.time() - 1000))
        # A fresh second attempt is blocked.
        self.assertFalse(results_store.acquire_lock(self.sid, now=time.time() - 900))
        # Fifteen minutes later the crashed lock is stale.
        self.assertTrue(results_store.acquire_lock(self.sid, now=time.time()))
        self.assertFalse(results_store.result_is_saved(self.sid))
        results_store.write_result(self.sid, {"video.mp4": b"video"}, {"report_mode": "coach"})
        self.assertTrue(results_store.result_is_saved(self.sid))
        self.assertFalse(results_store.acquire_lock(self.sid, now=time.time() + 99999))
        meta = results_store.read_meta(self.sid)
        self.assertEqual(meta["status"], "complete")
        self.assertEqual(meta["report_mode"], "coach")
        # The replace leaves no temp file next to meta.json.
        names = os.listdir(results_store.session_dir(self.sid))
        self.assertFalse(any(name.endswith(".tmp") for name in names))

    def test_email_marks_sending_before_the_request_and_never_resends(self):
        os.environ["RESEND_API_KEY"] = "test-key"
        results_store.write_result(self.sid, {"video.mp4": b"v"}, {"report_mode": "swimmer"})
        seen = []

        class Response:
            status = 200

            def read(self):
                return b"{}"

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        def opener(request, timeout=20):
            seen.append(results_store.read_meta(self.sid)["email_status"])
            return Response()

        try:
            self.assertEqual(results_store.send_report_link(self.sid, "swimmer@example.com", opener), "sent")
            self.assertEqual(seen, ["sending"])
            self.assertEqual(results_store.read_meta(self.sid)["email_status"], "sent")
            self.assertEqual(results_store.send_report_link(self.sid, "swimmer@example.com", opener), "sent")
            self.assertEqual(seen, ["sending"])
        finally:
            os.environ.pop("RESEND_API_KEY", None)

    def test_a_sending_record_is_not_resent_after_a_failed_request(self):
        os.environ["RESEND_API_KEY"] = "test-key"
        results_store.write_result(self.sid, {"video.mp4": b"v"}, {"report_mode": "swimmer"})
        calls = {"n": 0}

        def opener(request, timeout=20):
            calls["n"] += 1
            raise OSError("network down")

        try:
            self.assertEqual(results_store.send_report_link(self.sid, "swimmer@example.com", opener), "sending")
            self.assertEqual(results_store.read_meta(self.sid)["email_status"], "sending")
            self.assertEqual(results_store.send_report_link(self.sid, "swimmer@example.com", opener), "sending")
            self.assertEqual(calls["n"], 1)
            with open(results_store._meta_path(self.sid)) as handle:
                raw = json.loads(handle.read())
            self.assertEqual(raw["email_status"], "sending")
        finally:
            os.environ.pop("RESEND_API_KEY", None)


if __name__ == "__main__":
    unittest.main()
