from __future__ import annotations

import numpy as np
from rapidfuzz import fuzz, process

from ...model import ContactRecord
from .. import normalisation

NAME_THRESHOLD = 90 # good balance of false positives vs missed matches, based on spot checks
COMPANY_THRESHOLD = 40 # same, but company names are often longer so a few minor differences can drag the score down more than for personal names

# Candidates are scored against the whole secondary pool in C via process.cdist
# (multithreaded), one block at a time so the score matrix stays small.
_CHUNK = 2000


def fuzzy_key(
    candidates: list[ContactRecord],
    secondary: list[ContactRecord],
) -> dict[int, tuple[ContactRecord, int]]:
    """Confidence: name AND company each fuzzy-match independently.

    Scoring the concatenated 'name|company' key as one string lets a long
    shared company name drag the overall score above threshold even when the
    names share nothing. Comparing the two parts separately, with their own
    cutoffs, prevents that.

    The name comparison is the strict gate, so it runs first as a vectorised
    `process.cdist` with `score_cutoff=NAME_THRESHOLD`: every name pair is scored
    in C and sub-threshold pairs are zeroed. Only the sparse survivors then get
    the (looser, cheaper-to-fail) company check, in original secondary order so
    the best-match tie-break is unchanged.
    """
    # Pre-extract normalised (name, company, record) tuples once. Records that
    # can't form a usable key (missing name or company) are skipped here.
    sec_names: list[str] = []
    sec_companies: list[str] = []
    sec_records: list[ContactRecord] = []
    for r in secondary:
        if r.company is None:
            continue
        name = r.resolved_full_name()
        if name is None:
            continue
        sec_names.append(normalisation.normalise_string(name))
        sec_companies.append(normalisation.normalise_company(r.company, r.country))
        sec_records.append(r)

    if not sec_records:
        return {}

    # Candidate features, keeping each row's original index for the result map.
    cand_idx: list[int] = []
    q_names: list[str] = []
    q_companies: list[str] = []
    for i, candidate in enumerate(candidates):
        if candidate.company is None:
            continue
        cand_name = candidate.resolved_full_name()
        if cand_name is None:
            continue
        cand_idx.append(i)
        q_names.append(normalisation.normalise_string(cand_name))
        q_companies.append(normalisation.normalise_company(candidate.company, candidate.country))

    if not q_names:
        return {}

    matches: dict[int, tuple[ContactRecord, int]] = {}
    for start in range(0, len(q_names), _CHUNK):
        block = q_names[start:start + _CHUNK]
        name_scores = process.cdist(
            block, sec_names,
            scorer=fuzz.token_set_ratio,
            score_cutoff=NAME_THRESHOLD,
            dtype=np.float64,
            workers=-1,
        )
        for bi, row in enumerate(name_scores):
            survivors = np.nonzero(row)[0]  # columns with name_score >= NAME_THRESHOLD
            if survivors.size == 0:
                continue
            qi = start + bi
            q_company = q_companies[qi]
            best_record: ContactRecord | None = None
            best_score = 0
            for j in survivors:  # ascending == original secondary order
                company_score = fuzz.token_set_ratio(q_company, sec_companies[j])
                if company_score < COMPANY_THRESHOLD:
                    continue
                # Mean is more forgiving than min; min is more conservative. Mean
                # surfaces "both pretty good" as a high confidence; min would
                # report a 99/85 match as 85.
                combined = (float(row[j]) + company_score) // 2
                if combined > best_score:
                    best_score = combined
                    best_record = sec_records[j]
            if best_record is not None:
                matches[cand_idx[qi]] = (best_record, best_score)
    return matches
