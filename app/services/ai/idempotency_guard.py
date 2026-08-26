"""
Duplicate Submission Guard & Idempotency Engine
===============================================
Prevents accidental double-clicks and repeated submissions for:
- Payments / action requests
- Form submissions
- Admin approvals
Combines client-side double-click prevention with backend sliding-window idempotency.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from functools import wraps
from typing import Any, Dict, Optional, Tuple

from flask import jsonify, request, session

logger = logging.getLogger(__name__)

# Sliding window cache: hash -> (timestamp, response_data)
_IDEMPOTENCY_CACHE: Dict[str, Tuple[float, Any]] = {}
_WINDOW_SECONDS = 4.0


class IdempotencyGuard:
    """Duplicate Submission & Idempotency Guard."""

    @classmethod
    def check_and_record(
        cls,
        user_id: Optional[int],
        action_key: str,
        payload_data: Optional[Dict[str, Any]] = None,
        custom_key: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Checks if an identical submission occurred in the last _WINDOW_SECONDS.
        Returns: (is_duplicate: bool, warning_message: str)
        """
        now = time.time()

        # Clean expired cache entries
        expired_keys = [k for k, (t, _) in _IDEMPOTENCY_CACHE.items() if now - t > _WINDOW_SECONDS * 5]
        for k in expired_keys:
            _IDEMPOTENCY_CACHE.pop(k, None)

        # Generate request signature
        if custom_key:
            sig = f"custom:{custom_key}"
        else:
            raw = f"{user_id or 'anon'}:{action_key}:{json.dumps(payload_data or {}, sort_keys=True)}"
            sig = hashlib.sha256(raw.encode()).hexdigest()

        if sig in _IDEMPOTENCY_CACHE:
            ts, _ = _IDEMPOTENCY_CACHE[sig]
            if (now - ts) < _WINDOW_SECONDS:
                logger.warning(f"Duplicate submission prevented for action: {action_key} (sig: {sig[:8]})")
                return True, "Duplicate submission detected. Please wait a moment."

        # Record this submission
        _IDEMPOTENCY_CACHE[sig] = (now, True)
        return False, None


def prevent_duplicate_submissions(action_key: str = "generic_action"):
    """
    Route decorator that enforces duplicate submission protection.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = session.get("user_id")
            payload = request.get_json(silent=True) or request.form.to_dict()
            custom_key = request.headers.get("X-Idempotency-Key") or request.headers.get("X-Submission-Id")

            is_dup, msg = IdempotencyGuard.check_and_record(
                user_id=user_id,
                action_key=action_key or request.path,
                payload_data=payload,
                custom_key=custom_key,
            )

            if is_dup:
                return jsonify({
                    "error": "Duplicate submission prevented.",
                    "message": msg or "Your request is already being processed. Please do not submit repeatedly.",
                    "status": "duplicate_blocked",
                }), 409

            return f(*args, **kwargs)
        return decorated_function
    return decorator
