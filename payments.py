"""Stripe checkout checks shared by the landing page and the dashboard.

One query parameter, `session_id`, is the payment. It is checked against a
fixed pattern before it is used as a directory name or sent to Stripe.
"""
import logging
import os
import re

SESSION_ID_RE = re.compile(r"^cs_(test|live)_[A-Za-z0-9]{10,120}$")
# Coach checkout is $6.99. Swimmer checkout is $0.99 (or the old $4.99).
# Metadata wins when the payment link sets report_mode. The amount is the fallback.
COACH_AMOUNT_CENTS = 500


def valid_session_id(session_id: str) -> bool:
    return bool(session_id) and SESSION_ID_RE.fullmatch(session_id) is not None


def report_mode_from_checkout(session) -> str:
    metadata = getattr(session, "metadata", None) or {}
    mode = metadata.get("report_mode") if hasattr(metadata, "get") else None
    if mode in ("swimmer", "coach"):
        return mode
    try:
        amount = int(getattr(session, "amount_total", 0) or 0)
    except (TypeError, ValueError):
        amount = 0
    return "coach" if amount >= COACH_AMOUNT_CENTS else "swimmer"


def email_from_checkout(session) -> str:
    details = getattr(session, "customer_details", None)
    email = None
    if details is not None:
        email = details.get("email") if isinstance(details, dict) else getattr(details, "email", None)
    if not email:
        email = getattr(session, "customer_email", None) or ""
    return email or ""


def retrieve_paid_checkout(session_id: str):
    """Return (paid, report_mode, email).

    An id that fails the pattern is not sent to Stripe. Stripe errors come
    back as not-paid; the exception text is not logged (it can echo the id).
    """
    if not valid_session_id(session_id):
        return False, "swimmer", ""
    try:
        import stripe
    except ImportError:
        return False, "swimmer", ""
    key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not key:
        return False, "swimmer", ""
    stripe.api_key = key
    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception as exc:
        logging.error("Stripe verification failed (%s)", type(exc).__name__)
        return False, "swimmer", ""
    if getattr(session, "payment_status", None) != "paid":
        return False, report_mode_from_checkout(session), email_from_checkout(session)
    return True, report_mode_from_checkout(session), email_from_checkout(session)
