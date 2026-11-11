"""Rebuild viewer/swimform_freestyle_3d.html from viewer/src.html.

The HTML in git is generated. Edit src.html, then run this file.
"""
import base64
import os

ROOT = os.path.dirname(os.path.abspath(__file__))


def _read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as handle:
        return handle.read()


def main():
    page = _read("src.html")
    page = page.replace("/*__THREE__*/", _read("lib/three.min.js").replace("</script", "<\\/script"))
    page = page.replace("/*__ORBIT__*/", _read("lib/OrbitControls.js").replace("</script", "<\\/script"))
    page = page.replace("/*__GLTF__*/", _read("lib/GLTFLoader.js").replace("</script", "<\\/script"))
    with open(os.path.join(ROOT, "assets", "xbot.glb"), "rb") as handle:
        encoded = base64.b64encode(handle.read()).decode("ascii")
    page = page.replace("__XBOT_B64__", encoded)
    out = os.path.join(ROOT, "swimform_freestyle_3d.html")
    with open(out, "w", encoding="utf-8") as handle:
        handle.write(page)
    print(out, len(page))


if __name__ == "__main__":
    main()
