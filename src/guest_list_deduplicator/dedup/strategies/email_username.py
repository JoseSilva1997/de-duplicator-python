"""Strategy: match by normalised email localpart, with role-address and short-localpart guards."""
from __future__ import annotations

import re
from collections import defaultdict

from rapidfuzz import fuzz

from ...model import ContactRecord
from .. import normalisation

# Role and shared-mailbox localparts. A match on one of these belongs to an
# organisation rather than a person, so it must never produce a match or seed
# a transitive pass. Compared against the normalised localpart, so "no-reply"
# is checked as "noreply".
ROLE_LOCALPARTS = frozenset({
    "contact", "info", "admin", "administrator", "sales", "office", "hello",
    "support", "enquiries", "enquiry", "hr", "marketing", "team", "careers",
    "career", "jobs", "mail", "email", "help", "noreply", "donotreply",
    "newsletter", "press", "media", "general", "reception", "accounts",
    "billing", "finance", "service", "services", "webmaster", "postmaster",
})

# A localpart is considered distinctive (trusted without name corroboration) if
# it contained a separator or digit, or its normalised form is at least this many
# characters long. Short bare localparts (e.g. a four-letter first name) collide
# between different people, so those require the names to agree as well.
DISTINCTIVE_MIN_LENGTH = 8

# Name-corroboration thresholds used when a localpart is not distinctive.
# Deliberately looser than fuzzy_name: a shared localpart across domains is
# already strong evidence, so the names only need to not contradict each other.
_FIRST_THRESHOLD = 85
_LAST_THRESHOLD = 80
_FULLNAME_THRESHOLD = 80

_SEPARATORS = re.compile(r"[._-]")


def email_username(
        candidates: list[ContactRecord],
        secondary: list[ContactRecord],
) -> dict[int, tuple[ContactRecord, int]]:
    """Match candidates against secondary by normalised email localpart. Confidence 90.

    By the time this runs, exact_email has already claimed whole-email matches,
    so any hit here is a localpart-only match across different domains. The
    localpart is normalised (lowercased, '+suffix' dropped, '._-' stripped) so
    "john.smith" and "johnsmith" match. Two guards prevent over-matching: role
    and shared-mailbox localparts never match, and short bare localparts only
    match when the names agree.
    """
    by_key: dict[str, list[ContactRecord]] = defaultdict(list)  # localpart key -> secondary records with that key
    for record in secondary:
        feats = _localpart_features(record.email)
        if feats is not None and feats[0] not in ROLE_LOCALPARTS:
            by_key[feats[0]].append(record)

    matches: dict[int, tuple[ContactRecord, int]] = {}
    for i, candidate in enumerate(candidates):
        feats = _localpart_features(candidate.email)
        if feats is None or feats[0] in ROLE_LOCALPARTS:
            continue
        key, distinctive = feats
        for record in by_key.get(key, ()):
            if distinctive or _names_agree(candidate, record):
                matches[i] = (record, 90)
                break
    return matches


def _localpart_features(email: str | None) -> tuple[str, bool] | None:
    """Return (normalised localpart key, is_distinctive) or None if the email is unusable.

    The key drops any '+suffix' and strips '._-' so separator variants collide.
    A localpart is distinctive if the raw form contained a separator or digit,
    or the key is at least DISTINCTIVE_MIN_LENGTH characters long. If there is
    no '@', the whole string is treated as the localpart."""
    if email is None:
        return None
    at = email.find("@")
    raw = (email[:at] if at >= 0 else email).lower().split("+", 1)[0]
    key = _SEPARATORS.sub("", raw)
    if not key:
        return None
    distinctive = raw != key or any(c.isdigit() for c in raw) or len(key) >= DISTINCTIVE_MIN_LENGTH
    return key, distinctive


def _names_agree(a: ContactRecord, b: ContactRecord) -> bool:
    """Check whether the names on two records are compatible for a non-distinctive
    localpart match. When both sides have a first and last name, they are compared
    part by part; otherwise the resolved full names are compared. If either side
    has no usable name the check passes, letting the localpart match stand alone."""
    if a.first_name and a.last_name and b.first_name and b.last_name:
        first = fuzz.token_set_ratio(
            normalisation.normalise_string(a.first_name),
            normalisation.normalise_string(b.first_name),
        )
        if first < _FIRST_THRESHOLD:
            return False
        last = fuzz.token_set_ratio(
            normalisation.normalise_string(a.last_name),
            normalisation.normalise_string(b.last_name),
        )
        return last >= _LAST_THRESHOLD

    a_name = a.resolved_full_name()
    b_name = b.resolved_full_name()
    if a_name is None or b_name is None:
        return True
    return fuzz.token_set_ratio(
        normalisation.normalise_string(a_name),
        normalisation.normalise_string(b_name),
    ) >= _FULLNAME_THRESHOLD
