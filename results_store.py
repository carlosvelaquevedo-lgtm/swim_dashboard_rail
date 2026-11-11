"""Saved reports for one paid checkout.

Off unless SWIMFORM_RESULTS_DIR is set. That directory is meant to be a
Railway volume. Trade-offs, which have to be accepted before this is used
in production:

- The volume attaches to a single replica. The service cannot scale past
  one instance while the volume is mounted.
- A redeploy restarts that one instance, so the site is briefly down and any
  analysis still running dies. The lock it leaves is ignored after 15 minutes,
  and the payment can be tried again because no meta.json was written.
- The volume survives deploys. It is not a backup. Deleting it deletes the
  saved reports.

A payment is used up only when meta.json exists. The lock is a separate
file so a crash does not look like a finished report.
"""
import json
import logging
import os
import pickle
import tempfile
import time
import urllib.error
import urllib.request

from payments import valid_session_id

LOCK_STALE_SECONDS = 15 * 60
META_NAME = "meta.json"
LOCK_NAME = ".lock"
EMAIL_MARKER = ".email_sending"


def persistence_enabled() -> bool:
    return bool(os.environ.get("SWIMFORM_RESULTS_DIR", "").strip())


def _root() -> str:
    root = os.environ.get("SWIMFORM_RESULTS_DIR", "").strip()
    if not root:
        raise RuntimeError("SWIMFORM_RESULTS_DIR is not set")
    return root


def session_dir(session_id: str) -> str:
    if not valid_session_id(session_id):
        raise ValueError("invalid session id")
    path = os.path.join(_root(), session_id)
    # The id has no slashes, so this cannot escape the root.
    if os.path.dirname(os.path.normpath(path)) != os.path.normpath(_root()):
        raise ValueError("invalid session id")
    return path


def _meta_path(session_id: str) -> str:
    return os.path.join(session_dir(session_id), META_NAME)


def atomic_write_json(path: str, data: dict) -> None:
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(data, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_meta(session_id: str):
    if not persistence_enabled():
        return None
    path = _meta_path(session_id)
    if not os.path.exists(path):
        return None
    with open(path) as handle:
        return json.load(handle)


def result_is_saved(session_id: str) -> bool:
    """True only when a finished report was written. A lock alone does not count."""
    if not persistence_enabled() or not valid_session_id(session_id):
        return False
    return os.path.exists(_meta_path(session_id))


def acquire_lock(session_id: str, now: float = None) -> bool:
    """False when a report already exists or a fresh lock is held.

    A lock older than 15 minutes is removed so a crashed run can be retried.
    """
    if not persistence_enabled():
        return True
    if result_is_saved(session_id):
        return False
    directory = session_dir(session_id)
    os.makedirs(directory, exist_ok=True)
    lock_path = os.path.join(directory, LOCK_NAME)
    now = time.time() if now is None else now
    if os.path.exists(lock_path):
        try:
            with open(lock_path) as handle:
                started = float(handle.read().strip())
        except (OSError, ValueError):
            started = os.path.getmtime(lock_path)
        if now - started < LOCK_STALE_SECONDS:
            return False
        try:
            os.unlink(lock_path)
        except OSError:
            return False
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w") as handle:
        handle.write(str(now))
    return True


def release_lock(session_id: str) -> None:
    if not persistence_enabled() or not valid_session_id(session_id):
        return
    try:
        os.unlink(os.path.join(session_dir(session_id), LOCK_NAME))
    except OSError:
        pass


def write_result(session_id: str, files: dict, meta: dict) -> None:
    """Write artifacts, then meta.json last. No meta.json means the credit is unused."""
    if not persistence_enabled():
        return
    directory = session_dir(session_id)
    os.makedirs(directory, exist_ok=True)
    for name, content in files.items():
        if content is None:
            continue
        if os.path.basename(name) != name:
            raise ValueError("invalid artifact name")
        target = os.path.join(directory, name)
        fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, target)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    meta = dict(meta)
    meta["status"] = "complete"
    atomic_write_json(_meta_path(session_id), meta)


class _SummaryUnpickler(pickle.Unpickler):
    def __init__(self, file, allowed):
        super().__init__(file)
        self.allowed = allowed

    def find_class(self, module, name):
        if name in self.allowed:
            return self.allowed[name]
        if module == "builtins" or module.startswith("numpy") or module == "numpy":
            return super().find_class(module, name)
        raise pickle.UnpicklingError(f"refused {module}.{name}")


def load_summary(session_id: str, allowed: dict):
    path = os.path.join(session_dir(session_id), "summary.pkl")
    with open(path, "rb") as handle:
        return _SummaryUnpickler(handle, allowed).load()


def load_bytes(session_id: str, name: str):
    if os.path.basename(name) != name:
        raise ValueError("invalid artifact name")
    path = os.path.join(session_dir(session_id), name)
    if not os.path.exists(path):
        return None
    with open(path, "rb") as handle:
        return handle.read()


def report_url(session_id: str) -> str:
    base = os.environ.get("APP_BASE_URL", "https://swimform-ai.com").rstrip("/")
    return f"{base}/?session_id={session_id}"


def send_report_link(session_id: str, email: str, opener=None):
    """Email the report link once.

    Writes email_status "sending" before the request and "sent" after.
    A record already marked sending or sent is never sent again, including
    when the first attempt crashed after "sending".
    Returns the status string.
    """
    if not persistence_enabled() or not email or not result_is_saved(session_id):
        return "skipped"
    meta = read_meta(session_id) or {}
    if meta.get("email_status") in ("sending", "sent"):
        return meta["email_status"]
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key:
        return "skipped"
    marker = os.path.join(session_dir(session_id), EMAIL_MARKER)
    try:
        fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except FileExistsError:
        return "sending"

    meta["email"] = email
    meta["email_status"] = "sending"
    atomic_write_json(_meta_path(session_id), meta)

    sender = os.environ.get("RESEND_FROM", "SwimForm AI <info@swimform-ai.com>")
    url = report_url(session_id)
    payload = json.dumps({
        "from": sender,
        "to": [email],
        "subject": "Your SwimForm analysis is ready",
        "html": (
            "<p>Your freestyle analysis is ready.</p>"
            f'<p><a href="{url}">Open your report</a></p>'
            "<p>This link is for this analysis. Each purchase covers one video.</p>"
        ),
    }).encode()
    request = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    open_url = opener or urllib.request.urlopen
    try:
        with open_url(request, timeout=20) as response:
            status = getattr(response, "status", 200)
            if hasattr(response, "read"):
                response.read()
            if status >= 400:
                raise RuntimeError(f"email provider status {status}")
    except (OSError, urllib.error.URLError, RuntimeError):
        logging.error("Report email failed after it was marked sending")
        return "sending"

    meta = read_meta(session_id) or meta
    meta["email_status"] = "sent"
    atomic_write_json(_meta_path(session_id), meta)
    return "sent"
