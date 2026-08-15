"""Application utility helpers."""

from datetime import datetime, timezone


def utcnow():
    """Return current UTC time as a naive datetime."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
