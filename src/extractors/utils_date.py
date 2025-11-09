from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

def utc_timestamp_to_iso(timestamp: Optional[float]) -> Optional[str]:
    """
    Convert a Reddit created_utc timestamp to ISO-8601 format with +0000 suffix.

    Reddit timestamps are seconds since the Unix epoch in UTC.
    """
    if timestamp is None:
        return None
    try:
        dt = datetime.fromtimestamp(float(timestamp), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None
    # Format with explicit +0000 offset to match the example format
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f%z")