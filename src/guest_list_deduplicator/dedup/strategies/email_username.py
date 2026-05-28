from __future__ import annotations

from ...model import ContactRecord


def email_username(
    candidates: list[ContactRecord],
    secondary: list[ContactRecord],
) -> dict[int, tuple[ContactRecord, int]]:
    """Confidence 90: the part before '@' matches."""
    raise NotImplementedError
