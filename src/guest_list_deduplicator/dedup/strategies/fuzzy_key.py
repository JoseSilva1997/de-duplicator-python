from __future__ import annotations

from ...model import ContactRecord
from rapidfuzz import fuzz
from .. import normalisation

NAME_THRESHOLD = 90 # good balance of false positives vs missed matches, based on spot checks
COMPANY_THRESHOLD = 40 # same, but company names are often longer so a few minor differences can drag the score down more than for personal names


def fuzzy_key(
    candidates: list[ContactRecord],
    secondary: list[ContactRecord],
) -> dict[int, tuple[ContactRecord, int]]:
    """Confidence: name AND company each fuzzy-match independently.

    Scoring the concatenated 'name|company' key as one string lets a long
    shared company name drag the overall score above threshold even when the
    names share nothing. Comparing the two parts separately, with their own
    cutoffs, prevents that.
    """
    # Pre-extract normalised (name, company, record) tuples once. Records that
    # can't form a usable key (missing name or company) are skipped here.
    sec_pre: list[tuple[str, str, ContactRecord]] = []
    for r in secondary:
        if r.company is None:
            continue
        name = r.resolved_full_name()
        if name is None:
            continue
        sec_pre.append((
            normalisation.normalise_string(name),
            normalisation.normalise_company(r.company, r.country),
            r,
        ))

    if not sec_pre:
        return {}

    matches: dict[int, tuple[ContactRecord, int]] = {}
    for i, candidate in enumerate(candidates):
        if candidate.company is None:
            continue
        cand_name = candidate.resolved_full_name()
        if cand_name is None:
            continue
        q_name = normalisation.normalise_string(cand_name)
        q_company = normalisation.normalise_company(candidate.company, candidate.country)

        # No process.extractOne here because the cutoff is two-dimensional.
        # O(N*M) scan, but each ratio call is cheap.
        best_record: ContactRecord | None = None
        best_score = 0
        for s_name, s_company, s_record in sec_pre:
            name_score = fuzz.token_set_ratio(q_name, s_name)
            if name_score < NAME_THRESHOLD:
                continue
            company_score = fuzz.token_set_ratio(q_company, s_company)
            if company_score < COMPANY_THRESHOLD:
                continue
            # Mean is more forgiving than min; min is more conservative. Mean
            # surfaces "both pretty good" as a high confidence; min would
            # report a 99/85 match as 85.
            combined = (name_score + company_score) // 2
            if combined > best_score:
                best_score = combined
                best_record = s_record

        if best_record is not None:
            matches[i] = (best_record, best_score)
    return matches