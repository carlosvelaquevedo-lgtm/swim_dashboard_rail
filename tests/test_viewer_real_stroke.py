"""Headless Chrome check that a real stroke drives the viewer.

Resolves Chrome from CHROME_PATH, then from Playwright's bundled chromium.
Fails when neither browser is installed.
"""
import os
import unittest

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

CAPTIONS = """() => {
  function row(sel) {
    const el = document.querySelector(sel);
    if (!el) return {present: false, hidden: true, text: ''};
    const style = getComputedStyle(el);
    const hidden = style.display === 'none' || style.visibility === 'hidden' || !!el.hidden;
    return {present: true, hidden: hidden, text: el.textContent || ''};
  }
  return {
    pill: row('.top-pill-container'),
    subtitle: row('.intro-bar p'),
    heading: row('.panel-card .panel-sub')
  };
}"""


def resolve_chrome():
    """CHROME_PATH when that file exists, otherwise Playwright's chromium."""
    env = os.environ.get("CHROME_PATH", "").strip()
    if env and os.path.isfile(env):
        return env
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    with sync_playwright() as playwright:
        path = playwright.chromium.executable_path
    if path and os.path.isfile(path):
        return path
    return None


class ViewerRealStrokeTests(unittest.TestCase):
    def _captions(self, page):
        return page.evaluate(CAPTIONS)

    def _assert_modeled_copy(self, page, hidden):
        rows = self._captions(page)
        for name, row in rows.items():
            self.assertTrue(row["present"], name)
            self.assertEqual(row["hidden"], hidden, name)
        if not hidden:
            self.assertIn("Dropped elbow", rows["pill"]["text"])
            self.assertIn("A modeled stroke with four common faults", rows["subtitle"]["text"])
            self.assertIn("one full stroke loop", rows["heading"]["text"])

    def test_real_stroke_plays_and_switches_mode(self):
        chrome = resolve_chrome()
        if not chrome:
            self.fail("No Chrome found. Set CHROME_PATH or install Playwright chromium.")
        if not os.path.exists(HTML):
            self.fail("Built viewer is missing: " + HTML)
        from playwright.sync_api import sync_playwright

        errors = []
        launch_args = [
            "--use-gl=angle", "--use-angle=swiftshader",
            "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist",
            "--allow-file-access-from-files",
        ]
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=chrome, args=launch_args)
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
            self._assert_modeled_copy(page, True)
            page.click("#mode-target")
            page.wait_for_timeout(300)
            self.assertEqual(page.evaluate("window.__swimform.state.mode"), "target")
            self._assert_modeled_copy(page, False)
            page.click("#mode-side")
            page.wait_for_timeout(200)
            self.assertEqual(page.evaluate("window.__swimform.state.mode"), "side")
            self._assert_modeled_copy(page, True)
            page.click("#mode-real")
            self.assertIsNotNone(page.evaluate("window.__swimform.sampleRealPose(0.1)"))
            self._assert_modeled_copy(page, True)

            demo = browser.new_page(viewport={"width": 1400, "height": 900})
            demo.goto("file://" + os.path.abspath(HTML))
            demo.wait_for_function(
                "document.getElementById('ref-pill').textContent.length > 0",
                timeout=60000,
            )
            self.assertIsNone(demo.evaluate("window.__swimform.state.mode"))
            self._assert_modeled_copy(demo, False)
            browser.close()
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
