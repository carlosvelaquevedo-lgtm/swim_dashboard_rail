"""Headless Chrome check that a real stroke drives the viewer.

Skips when Chrome is not installed, so a CPU-only CI run still passes.
"""
import os
import unittest

CHROME = "/usr/local/bin/google-chrome"
HTML = os.path.join(os.path.dirname(__file__), "..", "viewer", "swimform_freestyle_3d.html")

INIT = r"""
window.__REAL_STROKE_3D__ = (function () {
  function pose(roll, reach) {
    const neck = {x: 0.33, y: -0.10, z: 0};
    const a = {x: 1, y: 0, z: 0};
    const right = {x: 0, y: Math.sin(roll), z: Math.cos(roll)};
    const dorsal = {x: 0, y: Math.cos(roll), z: -Math.sin(roll)};
    function arm(side) {
      const S = {x: neck.x, y: neck.y, z: neck.z + side * 0.18};
      const E = {x: S.x + 0.05, y: S.y - 0.28, z: S.z + side * 0.02};
      const W = {x: E.x + reach, y: E.y - 0.12, z: E.z};
      return {S: S, E: E, W: W, pole: {x: 0, y: 0, z: side}, wBack: 0, wRelax: 0, wDown: 1};
    }
    return {
      pelvis: {x: neck.x - 0.45, y: neck.y, z: 0}, neck: neck, a: a,
      shF: {right: right, dorsal: dorsal}, hipF: {right: right, dorsal: dorsal},
      headRoll: roll, roll: roll, hipRoll: roll * 0.7,
      arms: {R: arm(1), L: arm(-1)},
      legs: {
        R: {thigh: {x: -1, y: 0.1, z: 0}, shin: {x: -0.8, y: -0.3, z: 0}},
        L: {thigh: {x: -1, y: -0.1, z: 0}, shin: {x: -0.8, y: 0.2, z: 0}}
      }
    };
  }
  return {fps: 30, duration_s: 0.4, frames: [pose(0.1, 0.05), pose(0.4, 0.12), pose(-0.2, 0.02), pose(0.0, 0.08)]};
})();
"""


class ViewerRealStrokeTests(unittest.TestCase):
    def test_real_stroke_plays_and_switches_mode(self):
        if not os.path.exists(CHROME) or not os.path.exists(HTML):
            self.skipTest("chrome or the built viewer is not on this machine")
        from playwright.sync_api import sync_playwright

        errors = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=CHROME,
                args=[
                    "--use-gl=angle", "--use-angle=swiftshader",
                    "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist",
                    "--allow-file-access-from-files",
                ],
            )
            page = browser.new_page(viewport={"width": 1400, "height": 900})
            page.add_init_script(INIT)
            page.on("pageerror", lambda err: errors.append(str(err)))
            page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
            page.goto("file://" + os.path.abspath(HTML))
            page.wait_for_function("document.body.dataset.realReport === '1'", timeout=60000)
            mode = page.evaluate("window.__swimform.state.mode")
            self.assertEqual(mode, "real")
            elbow = page.inner_text("#hud-elbow3d")
            self.assertIn("°", elbow)
            report = page.inner_text("#report-body")
            self.assertIn("°", report)
            page.click("#mode-target")
            page.wait_for_timeout(300)
            self.assertEqual(page.evaluate("window.__swimform.state.mode"), "target")
            page.click("#mode-side")
            page.wait_for_timeout(200)
            self.assertEqual(page.evaluate("window.__swimform.state.mode"), "side")
            page.click("#mode-real")
            self.assertIsNotNone(page.evaluate("window.__swimform.sampleRealPose(0.1)"))
            browser.close()
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
