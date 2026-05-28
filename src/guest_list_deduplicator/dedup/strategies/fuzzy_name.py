from __future__ import annotations

from ...model import ContactRecord


def fuzzy_name(
    candidates: list[ContactRecord],
    secondary: list[ContactRecord],
) -> dict[int, tuple[ContactRecord, int]]:
    """Per-match confidence (≥ 80): rapidfuzz token_set_ratio on the resolved
    name alone. No company required."""
    raise NotImplementedError
