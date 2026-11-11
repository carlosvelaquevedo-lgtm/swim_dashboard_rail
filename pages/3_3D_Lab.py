"""3D Stroke Lab. The 2D dashboard is not imported and its routes are unchanged.

Free demo, admin test, and a paid lab3d checkout land here from app.py.
Torch and the Modal package are not imported. A failed gate does not write
meta.json, so the paid credit stays unused.
"""
import base64
import hashlib
import json
import os
import shutil
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
from results_store import (
    begin_paid_lift,
    load_bytes,
    persistence_enabled,
    release_lab_lock,
    result_is_saved,
    send_report_link,
    write_result,
)
from video_preflight import (
    ANALYSIS_WINDOW_MAX,
    ANALYSIS_WINDOW_MIN,
    UNREADABLE_CLIP_LENGTH,
    consume_paid_access,
    lift_duration_seconds,
    should_write_lab_credit,
)

APP_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
VIEWER_PATH = os.path.join(APP_ROOT, "viewer", "swimform_freestyle_3d.html")
STATIC_DIR = os.path.join(APP_ROOT, "static")
STATIC_VIEWER_NAME = "swimform_freestyle_3d.html"
IS_DEV = os.environ.get("IS_DEV", "false").lower() == "true"


def _viewer_html():
    with open(VIEWER_PATH, encoding="utf-8") as handle:
        return handle.read()


def _ensure_static_viewer():
    """Copy the built viewer into static/ once, so reruns do not resend the file."""
    os.makedirs(STATIC_DIR, exist_ok=True)
    dest = os.path.join(STATIC_DIR, STATIC_VIEWER_NAME)
    if not os.path.isfile(VIEWER_PATH):
        return dest
    if not os.path.isfile(dest) or os.path.getmtime(VIEWER_PATH) > os.path.getmtime(dest):
        shutil.copyfile(VIEWER_PATH, dest)
    return dest


def _viewer_href(stroke=None):
    _ensure_static_viewer()
    if stroke is None:
        return "/app/static/" + STATIC_VIEWER_NAME
    blob = json.dumps(stroke).replace("</", "<\\/")
    name = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24] + ".html"
    folder = os.path.join(STATIC_DIR, "strokes")
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, name)
    if not os.path.isfile(dest):
        html = _viewer_html()
        html = html.replace(
            "<body>",
            "<body><script>window.__REAL_STROKE_3D__ = " + blob + ";</script>",
            1,
        )
        tmp = dest + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            handle.write(html)
        os.replace(tmp, dest)
    return "/app/static/strokes/" + name


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
          If the viewer above stays blank, use the link on the page to open the same file.
        </p>
        """,
        height=48,
    )
    href = _viewer_href(stroke)
    st.markdown(
        '<a href="' + href + '" target="_blank" rel="noopener noreferrer">Open the 3D viewer in a new tab</a>',
        unsafe_allow_html=True,
    )


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
    consume_paid_access(st.session_state)


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
    video_duration = lift_duration_seconds(meta.get("duration"))
    if video_duration is None:
        st.error(UNREADABLE_CLIP_LENGTH)
        return
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
    else:
        duration_s = min(video_duration, ANALYSIS_WINDOW_MAX)
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
    with open(out, "rb") as handle:
        mp4 = handle.read()
    try:
        os.unlink(out)
    except OSError:
        pass
    paid = st.session_state.get("lab_access") == "paid" and not admin
    sid = st.session_state.get("active_session_id")
    locked = False
    if paid:
        if not sid:
            st.error("This payment has no session, so the clip was not sent.")
            return
        status = begin_paid_lift(sid)
        if status == "saved":
            _show_saved(sid)
            return
        if status != "lift":
            st.error(
                "An analysis for this payment is already running. "
                "If it was interrupted, open the same link again in 15 minutes."
            )
            return
        locked = True
    try:
        with st.spinner("Lifting the stroke…"):
            try:
                payload = _call_modal(mp4, model_size)
            except Exception as exc:
                st.error("The 3D service did not answer (" + type(exc).__name__ + "). Nothing was saved.")
                return
        if payload.get("error") and not payload.get("gates"):
            st.error(payload["error"])
            return
        _render_result(payload)
    finally:
        if locked:
            release_lab_lock(sid)


def _show_saved(session_id):
    raw = load_bytes(session_id, "stroke3d.json")
    if raw:
        _show_viewer(json.loads(raw.decode("utf-8")))
    else:
        st.info("The saved 3D file could not be opened.")


access = st.session_state.get("lab_access")
if access == "demo" and not st.session_state.get("paid"):
    st.title("3D Stroke Lab")
    _demo()
elif access in ("admin", "paid") or (IS_DEV and st.session_state.get("report_mode") == "lab3d"):
    st.title("3D Stroke Lab")
    if access == "admin" or IS_DEV:
        st.caption("Admin test. Uploads are not charged. Gate numbers are shown in full.")
    saved_id = st.session_state.get("active_session_id")
    if access == "paid" and saved_id and result_is_saved(saved_id):
        _show_saved(saved_id)
    else:
        _upload_and_lift()
else:
    st.title("3D Stroke Lab")
    _demo()
