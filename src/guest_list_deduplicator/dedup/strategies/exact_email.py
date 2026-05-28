from __future__ import annotations

from ...model import ContactRecord


def exact_email(
        candidates: list[ContactRecord],
        secondary: list[ContactRecord],
) -> dict[int, tuple[ContactRecord, int]]:
    """Confidence 100: identical email address (already lowercased by
    ContactRecord.build, so plain equality is correct)."""
    # Build the lookup once. If multiple secondary records share an email, the
    # later one wins. This is fine, since any matching record is acceptable as the
    # "reason" we report in the removed-records output.
    email_to_record: dict[str, ContactRecord] = {}
    for record in secondary:
        if record.email is not None:
            email_to_record[record.email] = record

    matches: dict[int, tuple[ContactRecord, int]] = {}
    for i, candidate in enumerate(candidates):
        if candidate.email is not None and candidate.email in email_to_record:
            matches[i] = (email_to_record[candidate.email], 100)
    return matches
