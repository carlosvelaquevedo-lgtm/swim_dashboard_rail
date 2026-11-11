"""Paid 3D lab credit: one lift per session, no dashboard write, no uncapped clip."""
import os
import unittest

import results_store
import video_preflight as pre

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))


def _read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as handle:
        return handle.read()


class PaidLiftTests(unittest.TestCase):
    def setUp(self):
        self.tmp = __import__("tempfile").TemporaryDirectory()
        os.environ["SWIMFORM_RESULTS_DIR"] = self.tmp.name
        self.sid = "cs_test_" + "d" * 16

    def tearDown(self):
        os.environ.pop("SWIMFORM_RESULTS_DIR", None)
        self.tmp.cleanup()

    def test_second_lift_makes_no_modal_call(self):
        calls = []

        def modal():
            calls.append("modal")
            return {"ok": True}

        self.assertEqual(results_store.begin_paid_lift(self.sid), "lift")
        try:
            modal()
            results_store.write_result(
                self.sid, {"stroke3d.json": b"{}"}, {"report_mode": "lab3d"}
            )
        finally:
            results_store.release_lab_lock(self.sid)

        self.assertEqual(results_store.begin_paid_lift(self.sid), "saved")
        self.assertEqual(calls, ["modal"])
        lock = os.path.join(self.tmp.name, self.sid + ".lock")
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "lab3d-cache")))
        # A second attempt must not create a new lock or call Modal.
        self.assertFalse(os.path.exists(lock))

    def test_held_lock_blocks_a_second_tab(self):
        calls = []
        self.assertEqual(results_store.begin_paid_lift(self.sid), "lift")
        self.assertEqual(results_store.begin_paid_lift(self.sid), "busy")
        self.assertEqual(calls, [])
        results_store.release_lab_lock(self.sid)


class DashboardAndDurationTests(unittest.TestCase):
    def test_lab3d_session_on_the_dashboard_writes_nothing(self):
        sid = "cs_test_" + "e" * 16
        writes = []
        action, link = pre.dashboard_checkout_action("lab3d", sid, lambda: writes.append("write"))
        self.assertEqual(action, "lab")
        self.assertIn(sid, link)
        self.assertTrue(link.startswith("/?session_id="))
        self.assertEqual(writes, [])
        action, link = pre.dashboard_checkout_action("swimmer", sid, lambda: writes.append("write"))
        self.assertEqual(action, "analyze")
        self.assertIsNone(link)
        self.assertEqual(writes, ["write"])
        action, _link = pre.dashboard_checkout_action("coach", sid, lambda: writes.append("write"))
        self.assertEqual(action, "analyze")

    def test_unreadable_duration_blocks_modal(self):
        for value in (None, 0, 0.0, "N/A"):
            calls = []
            action, message = pre.guard_lift_duration(value, lambda: calls.append("modal"))
            self.assertEqual(action, "blocked", value)
            self.assertEqual(message, "Couldn't read clip length — re-export and try again")
            self.assertEqual(calls, [], value)
        action, payload = pre.guard_lift_duration(8.5, lambda: "sent")
        self.assertEqual(action, "ok")
        self.assertEqual(payload, "sent")
        self.assertEqual(pre.lift_duration_seconds(8.5), 8.5)
        self.assertLessEqual(min(pre.lift_duration_seconds(40), pre.ANALYSIS_WINDOW_MAX), 15.0)

    def test_successful_save_resets_paid_access(self):
        sid = "cs_test_" + "f" * 16
        state = {
            "paid": True,
            "active_session_id": sid,
            "consumed_session_ids": set(),
            "lab_access": "paid",
        }
        pre.consume_paid_access(state)
        self.assertFalse(state["paid"])
        self.assertIn(sid, state["consumed_session_ids"])
        self.assertEqual(state["credit_consumed_for_cache_key"], "lab3d:" + sid)
        self.assertEqual(state["lab_access"], "paid")


class LabPageSourceTests(unittest.TestCase):
    def test_lab_page_has_no_lift_cache_and_opens_a_new_tab(self):
        lab = _read("pages/3_3D_Lab.py")
        app = _read("app.py")
        viewer = _read("viewer/src.html")
        self.assertNotIn("lab3d-cache", lab)
        self.assertNotIn("_store_lift", lab)
        self.assertNotIn("_cached_lift", lab)
        self.assertNotIn("Open the 3D viewer in a new tab", lab.split("target=\"_blank\"")[0])
        self.assertIn('target="_blank"', lab)
        self.assertNotIn("st.download_button(", lab[lab.find("Open the 3D viewer"):lab.find("Open the 3D viewer") + 400] if "Open the 3D viewer" in lab else "st.download_button(")
        self.assertNotIn("Developer: Open 3D Lab", app)
        self.assertIn("Developer: Skip to Dashboard", app)
        self.assertIn("showModeledFaultCopy(mode === 'target')", viewer)
        self.assertIn("begin_paid_lift", lab)
        self.assertIn("lift_duration_seconds", lab)
        self.assertIn("UNREADABLE_CLIP_LENGTH", lab)
        self.assertEqual(
            pre.UNREADABLE_CLIP_LENGTH,
            "Couldn't read clip length — re-export and try again",
        )
        dashboard = _read("pages/2_Dashboard.py")
        self.assertIn("dashboard_checkout_action", dashboard)
