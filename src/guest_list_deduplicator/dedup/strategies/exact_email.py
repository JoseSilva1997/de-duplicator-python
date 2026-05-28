from __future__ import annotations

from ...model import ContactRecord


def exact_email(
    candidates: list[ContactRecord],
    secondary: list[ContactRecord],
) -> dict[int, tuple[ContactRecord, int]]:
    """Confidence 100: same email address (case-insensitive, already lowercased
    by ContactRecord.build)."""
    raise NotImplementedError
