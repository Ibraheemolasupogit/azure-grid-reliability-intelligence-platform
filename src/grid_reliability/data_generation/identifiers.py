"""Stable fictional identifier helpers."""

from __future__ import annotations

import hashlib


def stable_id(prefix: str, *parts: object, width: int = 10) -> str:
    """Create a deterministic identifier from domain parts."""
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    digest = hashlib.sha1(payload).hexdigest()[:width].upper()
    return f"{prefix}-{digest}"
