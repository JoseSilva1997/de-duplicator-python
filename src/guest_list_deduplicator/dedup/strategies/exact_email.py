"""exact_email strategy: match candidates against secondary records on identical email address."""
from __future__ import annotations

from ...model import ContactRecord


def exact_email(
        candidates: list[ContactRecord],
        secondary: list[ContactRecord],
) -> dict[int, tuple[ContactRecord, int]]:
    """Match candidates against secondary records on exact email address. Confidence: 100.

    Emails are lowercased by ContactRecord.build, so plain equality is sufficient.
    A confidence of 100 signals tautological certainty, distinguishing this strategy
    from the fuzzy ones further down the pipeline.
    """
    # Build a lookup from email to secondary record. When multiple secondary records
    # share an email, the last one wins; any matching record is acceptable as the
    # match reason reported in the output.
    email_to_record: dict[str, ContactRecord] = {}
    for record in secondary:
        if record.email is not None:
            email_to_record[record.email] = record

    matches: dict[int, tuple[ContactRecord, int]] = {}
    for i, candidate in enumerate(candidates):
        if candidate.email is not None and candidate.email in email_to_record:
            matches[i] = (email_to_record[candidate.email], 100)
    return matches
