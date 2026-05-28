from __future__ import annotations

from ...model import ContactRecord


def name_company_key(
    candidates: list[ContactRecord],
    secondary: list[ContactRecord],
) -> dict[int, tuple[ContactRecord, int]]:
    """Confidence 90: exact match on `normalised name | normalised company`.

    Per-row name check accepts FIRST_NAME + LAST_NAME OR FULL_NAME.
    """
    raise NotImplementedError
