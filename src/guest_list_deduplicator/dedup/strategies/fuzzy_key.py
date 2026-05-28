from __future__ import annotations

from ...model import ContactRecord


def fuzzy_key(
    candidates: list[ContactRecord],
    secondary: list[ContactRecord],
) -> dict[int, tuple[ContactRecord, int]]:
    """Confidence 85: rapidfuzz token_set_ratio on the name|company key ≥ threshold."""
    raise NotImplementedError
