"""3D Stroke Lab. The 2D dashboard is not imported and its routes are unchanged.

Free demo, admin test, and a paid lab3d checkout land here from app.py.
Torch and the Modal package are not imported. A failed gate does not write
meta.json, so the paid credit stays unused.
"""
import base64
import hashlib
import json
import os
import urllib.request

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="3D Stroke Lab", page_icon="🏊", layout="wide", initial_sidebar_state="collapsed")

from ingest import (
    MAX_UPLOAD_BYTES,
    UPLOAD_EXTENSIONS,
    extract_preview_jpeg,
    normalize_video_to_cfr,
    probe_video_metadata,
    upload_suffix,
    write_upload_to_temp,
)
from results_store import load_bytes, persistence_enabled, result_is_saved, send_report_link, write_result
from video_preflight import (
    ANALYSIS_WINDOW_MAX,
    ANALYSIS_WINDOW_MIN,
    should_write_lab_credit,
)

VIEWER_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "viewer", "swimform_freestyle_3d.html"))
IS_DEV = os.environ.get("IS_DEV", "false").lower() == "true"


def _viewer_html():
    with open(VIEWER_PATH, encoding="utf-8") as handle:
        return handle.read()


def _show_viewer(stroke=None):
    if not os.path.exists(VIEWER_PATH):
        st.error("The 3D viewer file is not in this build.")
        return
    html = _viewer_html()
    if stroke:
        blob = json.dumps(stroke).replace("</", "<\\/")
        html = html.replace("<body>", "<body><script>window.__REAL_STROKE_3D__ = " + blob + ";</script>", 1)
    components.html(html, height=980, scrolling=True)
    components.html(
        """
        <p style="font-family:sans-serif;color:#94a3b8;font-size:14px;margin:0;">
          If the viewer above stays blank, use the button in the page to open the same file.
        </p>
        """,
        height=48,
    )
    st.download_button(
        "Open the 3D viewer in a new tab",
        data=html.encode("utf-8"),
        file_name="swimform_freestyle_3d.html",
        mime="text/html",
        help="Phones sometimes will not load the viewer inside the page. Open this file in a new tab.",
    )


def _cache_file(digest):
    root = os.environ.get("SWIMFORM_RESULTS_DIR", "")
    if not root:
        return None
    folder = os.path.join(root, "lab3d-cache")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, digest + ".json")


def _cached_lift(digest):
    memory = st.session_state.setdefault("lab_gpu_cache", {})
    if digest in memory:
        return memory[digest]
    path = _cache_file(digest)
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        memory[digest] = payload
        return payload
    return None


def _store_lift(digest, payload):
    st.session_state.setdefault("lab_gpu_cache", {})[digest] = payload
    path = _cache_file(digest)
    if not path:
        return
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    os.replace(tmp, path)


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _call_modal(mp4_bytes, model_size):
    url = os.environ.get("MODAL_3D_URL", "")
    token = os.environ.get("MODAL_3D_TOKEN", "")
    if not url or not token:
        return {"ok": False, "error": "The 3D service is not configured."}
    body = json.dumps({
        "video_b64": base64.b64encode(mp4_bytes).decode("ascii"),
        "model_size": model_size,
    }).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))


def _gate_lines(gates):
    if not gates:
        return ["No gate report came back."]
    lines = []
    for key, label in (
        ("gate1_coverage", "Swimmer visible in the frames"),
        ("gate2_bone_cv", "Bone lengths stayed stable"),
        ("gate3_wrist_speed", "Wrist speed stayed realistic"),
    ):
        item = gates.get(key) or {}
        lines.append(("Pass" if item.get("passed") else "Fail") + " — " + label)
    lines.append("Depth is not measured from one camera. Roll and hand entry are estimates.")
    return lines


def _save_paid(stroke):
    session_id = st.session_state.get("active_session_id")
    if not should_write_lab_credit(True, st.session_state.get("lab_access"), st.session_state.get("is_admin_session")):
        return
    if not session_id or not persistence_enabled() or result_is_saved(session_id):
        return
    write_result(session_id, {
        "stroke3d.json": json.dumps(stroke).encode("utf-8"),
    }, {
        "report_mode": "lab3d",
        "email": st.session_state.get("customer_email", ""),
    })
    send_report_link(session_id, st.session_state.get("customer_email", ""))


def _render_result(payload):
    gates = payload.get("gates") or {}
    for line in _gate_lines(gates):
        st.write(line)
    if st.session_state.get("lab_access") == "admin" or IS_DEV:
        st.json(gates)
        if payload.get("stroke"):
            st.download_button(
                "Download stroke3d.json",
                data=json.dumps(payload["stroke"]).encode("utf-8"),
                file_name="stroke3d.json",
                mime="application/json",
            )
    if gates.get("passed") and payload.get("stroke"):
        _save_paid(payload["stroke"])
        _show_viewer(payload["stroke"])
        return
    st.error("This clip did not pass the 3D checks, so nothing was saved and the credit was not used.")
    st.write("Upload a closer clip on this same page, or run the 2D report instead.")
    if st.button("Run 2D Biomechanics Report Instead"):
        st.session_state.report_mode = "swimmer"
        st.session_state.lab_access = None
        st.switch_page("pages/2_Dashboard.py")


def _demo():
    st.info("This is a modeled stroke, not your video. Upload is unlocked after checkout.")
    link = os.environ.get("STRIPE_PAYMENT_LINK_3D", "")
    if link:
        st.link_button("Upload my video to the 3D lab", "?checkout=lab3d")
    st.link_button("Or get the $0.99 2D swimmer report", "/")
    _show_viewer()


def _upload_and_lift():
    admin = st.session_state.get("lab_access") == "admin" or (
        IS_DEV and st.session_state.get("is_admin_session")
    )
    st.subheader("Upload a clip")
    st.caption("GoPro, iPhone, and other phone files. Up to 500 MB. The lab analyzes at most 15 seconds at real-time speed.")
    uploaded = st.file_uploader("Swimming video", type=list(UPLOAD_EXTENSIONS))
    if not uploaded:
        return
    if uploaded.size > MAX_UPLOAD_BYTES:
        st.error("Video must be under 500 MB.")
        return
    stage_key = f"{uploaded.name}:{uploaded.size}"
    staged = st.session_state.get("lab_stage")
    if not staged or staged.get("key") != stage_key or not os.path.exists(staged.get("path", "")):
        if staged and staged.get("path") and staged.get("key") != stage_key:
            try:
                os.unlink(staged["path"])
            except OSError:
                pass
        path = write_upload_to_temp(uploaded, suffix=upload_suffix(uploaded.name))
        meta = probe_video_metadata(path)
        st.session_state["lab_stage"] = {"key": stage_key, "path": path, "meta": meta}
    else:
        path = staged["path"]
        meta = staged.get("meta")
    if not meta:
        st.error("This file has no video stream we can read.")
        st.session_state.pop("lab_stage", None)
        try:
            os.unlink(path)
        except OSError:
            pass
        return
    speed_label = st.selectbox(
        "Clip playback speed",
        ["1x Normal", "0.5x Slow-Mo", "0.25x (120fps Slow-Mo)", "0.125x (240fps Slow-Mo)"],
    )
    speed = {"1x Normal": 1.0, "0.5x Slow-Mo": 0.5, "0.25x (120fps Slow-Mo)": 0.25, "0.125x (240fps Slow-Mo)": 0.125}[speed_label]
    orientation_label = st.selectbox(
        "Orientation",
        ["Auto", "Flip 180 deg (upside-down GoPro pole)", "Rotate 90 deg CW", "Rotate 90 deg CCW"],
    )
    orientation = {
        "Auto": "auto",
        "Flip 180 deg (upside-down GoPro pole)": "flip180",
        "Rotate 90 deg CW": "rot90cw",
        "Rotate 90 deg CCW": "rot90ccw",
    }[orientation_label]
    undistort = False
    if meta.get("is_gopro"):
        undistort = st.checkbox("GoPro wide-lens undistort", value=False)
    start_s = 0.0
    duration_s = None
    video_duration = meta.get("duration") or 0
    if video_duration > ANALYSIS_WINDOW_MAX:
        window = st.slider(
            "Stroke window length (seconds)",
            min_value=ANALYSIS_WINDOW_MIN,
            max_value=float(min(ANALYSIS_WINDOW_MAX, video_duration)),
            value=min(12.0, ANALYSIS_WINDOW_MAX),
            step=0.5,
        )
        start_s = st.slider("Window start (seconds)", 0.0, float(max(0.0, video_duration - window)), 0.0, 0.5)
        duration_s = window
        cols = st.columns(3)
        for column, instant, label in zip(cols, (start_s, start_s + window / 2, start_s + window), ("Start", "Middle", "End")):
            jpeg = extract_preview_jpeg(path, instant)
            with column:
                st.caption(label)
                if jpeg:
                    st.image(jpeg)
    model_size = "base"
    if admin:
        model_size = st.selectbox("ViTPose size", ["base", "huge"], index=0)
    if not st.button("Lift this clip into 3D"):
        return
    with st.spinner("Normalizing the clip…"):
        out, ok, message = normalize_video_to_cfr(
            path,
            start_s=start_s,
            duration_s=duration_s,
            playback_speed=speed,
            orientation=orientation,
            undistort=bool(undistort),
            max_long_side=1920,
            video_stream_index=meta.get("video_stream_index"),
        )
    if path != out:
        try:
            os.unlink(path)
        except OSError:
            pass
        st.session_state.pop("lab_stage", None)
    if not ok:
        st.error("Could not normalize this file, so it was not sent to the GPU. " + message)
        return
    digest = _sha256(out)
    cached = _cached_lift(digest)
    if cached:
        st.caption("This exact clip was already lifted. Showing the saved result.")
        _render_result(cached)
        try:
            os.unlink(out)
        except OSError:
            pass
        return
    with open(out, "rb") as handle:
        mp4 = handle.read()
    try:
        os.unlink(out)
    except OSError:
        pass
    with st.spinner("Lifting the stroke…"):
        try:
            payload = _call_modal(mp4, model_size)
        except Exception as exc:
            st.error("The 3D service did not answer (" + type(exc).__name__ + "). Nothing was saved.")
            return
    if payload.get("error") and not payload.get("gates"):
        st.error(payload["error"])
        return
    _store_lift(digest, payload)
    _render_result(payload)


access = st.session_state.get("lab_access")
if access == "demo" and not st.session_state.get("paid"):
    st.title("3D Stroke Lab")
    _demo()
elif access in ("admin", "paid") or (IS_DEV and st.session_state.get("report_mode") == "lab3d"):
    st.title("3D Stroke Lab")
    if access == "admin" or IS_DEV:
        st.caption("Admin test. Uploads are not charged. Gate numbers are shown in full.")
    saved_id = st.session_state.get("active_session_id")
    if access == "paid" and saved_id and st.session_state.get("view_saved_report"):
        raw = load_bytes(saved_id, "stroke3d.json")
        if raw:
            _show_viewer(json.loads(raw.decode("utf-8")))
        else:
            st.info("The saved 3D file could not be opened.")
    else:
        _upload_and_lift()
else:
    st.title("3D Stroke Lab")
    _demo()
