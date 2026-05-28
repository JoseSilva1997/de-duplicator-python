from __future__ import annotations

from ...model import ContactRecord


def email_username(
        candidates: list[ContactRecord],
        secondary: list[ContactRecord],
) -> dict[int, tuple[ContactRecord, int]]:
    """Confidence 90: same username (the part before '@')."""
    # By the time this strategy runs, exact_email has already pulled out the
    # candidates whose entire email matched. So any match found here is a
    # username-only match — a different domain on each side.
    username_to_record: dict[str, ContactRecord] = {}
    for record in secondary:
        username = _get_username(record.email)
        if username is not None:
            username_to_record[username] = record

    matches: dict[int, tuple[ContactRecord, int]] = {}
    for i, candidate in enumerate(candidates):
        username = _get_username(candidate.email)
        if username is not None and username in username_to_record:
            matches[i] = (username_to_record[username], 90)
    return matches


def _get_username(email: str | None) -> str | None:
    # Pre-@ part. If there's no @, treat the whole string as the username so
    # that a candidate accidentally typed in as "foo" can still match a
    # secondary "foo@example.com". Cheap and rarely harmful.
    if email is None:
        return None
    at = email.find("@")
    return email[:at] if at >= 0 else email
