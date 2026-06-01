"""Strategy: match by exact normalised name-and-company key."""
from __future__ import annotations

from .. import normalisation
from ...model import ContactRecord


def name_company_key(
    candidates: list[ContactRecord],
    secondary: list[ContactRecord],
) -> dict[int, tuple[ContactRecord, int]]:
    """Match candidates against secondary by exact normalised name and company key.
    Confidence 90.

    A candidate is only eligible if it has a name (first+last or full) and a
    company. key_for returns None when either is missing, which naturally
    excludes those rows.
    """
    # Build a key-to-record index over secondary. key_for handles name
    # resolution and normalisation; missing name or company yields None and
    # those records are skipped.
    key_to_record: dict[str, ContactRecord] = {}
    for record in secondary:
        key = normalisation.key_for(record)
        if key is not None:
            key_to_record[key] = record

    matches: dict[int, tuple[ContactRecord, int]] = {}
    for i, candidate in enumerate(candidates):
        key = normalisation.key_for(candidate)
        if key is not None and key in key_to_record:
            matches[i] = (key_to_record[key], 90)
    return matches