from __future__ import annotations

from .. import normalisation
from ...model import ContactRecord


def name_company_key(
    candidates: list[ContactRecord],
    secondary: list[ContactRecord],
) -> dict[int, tuple[ContactRecord, int]]:
    """Confidence 90: exact match on '<normalised name>|<normalised company>'.

    Per-row gate: candidate must have a name (first+last OR full) and a
    company. key_for() returns None when either piece is missing, which
    naturally filters those rows out.
    """
    # Build the lookup. key_for handles the name-resolution and normalisation;
    # records missing a name or company produce None and are silently skipped.
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