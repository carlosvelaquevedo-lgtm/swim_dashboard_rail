import os
import uuid
import logging
import streamlit as st

try:
    from posthog import Posthog
    POSTHOG_AVAILABLE = True
except ImportError:
    POSTHOG_AVAILABLE = False

_posthog = None

def get_client():
    global _posthog
    if _posthog is None and POSTHOG_AVAILABLE:
        key = os.environ.get("POSTHOG_API_KEY")
        if not key:
            return None
        _posthog = Posthog(project_api_key=key, host="https://us.i.posthog.com")
    return _posthog

def get_distinct_id():
    if "ph_distinct_id" not in st.session_state:
        st.session_state.ph_distinct_id = str(uuid.uuid4())
    return st.session_state.ph_distinct_id

def track(event_name: str, properties: dict = None):
    client = get_client()
    if client is None:
        return
    try:
        client.capture(
            distinct_id=get_distinct_id(),
            event=event_name,
            properties=properties or {},
        )
    except Exception as e:
        logging.debug(f"PostHog tracking error: {e}")
        pass  # never let analytics break the app
