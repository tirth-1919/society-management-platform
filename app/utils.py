<<<<<<< HEAD
"""Application utility helpers."""
=======
﻿"""Application utility helpers."""
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32

from datetime import datetime, timezone


def utcnow():
    """Return current UTC time as a naive datetime."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
