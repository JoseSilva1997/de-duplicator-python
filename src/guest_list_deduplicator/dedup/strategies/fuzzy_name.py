from __future__ import annotations

from ...model import ContactRecord
from rapidfuzz import fuzz
from .. import normalisation

FIRST_NAME_THRESHOLD = 92 # token_set_ratio: lenient, handles initials and middle names
LAST_NAME_THRESHOLD = 90  # fuzz.ratio: strict, rejects "Garcia" vs "Garcia Lopez"
FULLNAME_THRESHOLD = 100  # fallback when first/last aren't separately available


def _split_parts(record: ContactRecord) -> tuple[str | None, str | None, str | None]:
    """Return (first, last, full) normalised. first/last are None unless both are present."""
    if record.first_name is not None and record.last_name is not None:
        return (
            normalisation.normalise_string(record.first_name),
            normalisation.normalise_string(record.last_name),
            None,
        )
    full = record.resolved_full_name()
    if full is None:
        return (None, None, None)
    return (None, None, normalisation.normalise_string(full))


def _country_key(record: ContactRecord) -> str | None:
    if record.country is None:
        return None
    return normalisation.normalise_string(record.country)


def _country_conflict(a: str | None, b: str | None) -> bool:
    """Veto: both sides declared a country and they disagree."""
    return a is not None and b is not None and a != b


def fuzzy_name(
    candidates: list[ContactRecord],
    secondary: list[ContactRecord],
) -> dict[int, tuple[ContactRecord, int]]:
    """Confidence: first name AND last name each fuzzy-match independently, with a
    country veto. The catch-all strategy when no email or company match exists.

    Last names use fuzz.ratio (no subset bonus) so "Garcia" doesn't collapse into
    "Garcia Lopez". First names use token_set_ratio to forgive middle names and
    initial variants. When the record only carries a full_name (no split), we fall
    back to whole-string token_set_ratio at an exact-match cutoff.
    """
    sec_pre: list[tuple[str | None, str | None, str | None, str | None, ContactRecord]] = []
    for r in secondary:
        first, last, full = _split_parts(r)
        if first is None and full is None:
            continue
        sec_pre.append((first, last, full, _country_key(r), r))

    if not sec_pre:
        return {}

    matches: dict[int, tuple[ContactRecord, int]] = {}
    for i, candidate in enumerate(candidates):
        q_first, q_last, q_full = _split_parts(candidate)
        if q_first is None and q_full is None:
            continue
        q_country = _country_key(candidate)

        best_record: ContactRecord | None = None
        best_score = 0
        for s_first, s_last, s_full, s_country, s_record in sec_pre:
            if _country_conflict(q_country, s_country):
                continue

            # Prefer the split path when both sides have it; otherwise fall back
            # to whole-string comparison. Mixing (one side split, one side full)
            # would require splitting the full_name heuristically, which is
            # exactly the failure mode we're trying to avoid, so we just use
            # the full-name path for those pairs too.
            if q_first is not None and s_first is not None:
                first_score = fuzz.token_set_ratio(q_first, s_first)
                if first_score < FIRST_NAME_THRESHOLD:
                    continue
                last_score = fuzz.ratio(q_last, s_last)
                if last_score < LAST_NAME_THRESHOLD:
                    continue
                combined = (first_score + last_score) // 2
            else:
                cand_full = q_full if q_full is not None else f"{q_first} {q_last}"
                sec_full = s_full if s_full is not None else f"{s_first} {s_last}"
                score = fuzz.token_set_ratio(cand_full, sec_full)
                if score < FULLNAME_THRESHOLD:
                    continue
                combined = score

            if combined > best_score:
                best_score = combined
                best_record = s_record

        if best_record is not None:
            matches[i] = (best_record, best_score)
    return matches
