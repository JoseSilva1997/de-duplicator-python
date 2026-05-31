from __future__ import annotations

from collections import defaultdict

import numpy as np
from rapidfuzz import fuzz, process

from ...model import ContactRecord
from .. import normalisation

NAME_THRESHOLD = 90 # good balance of false positives vs missed matches, based on spot checks
COMPANY_THRESHOLD = 40 # same, but company names are often longer so a few minor differences can drag the score down more than for personal names

# Candidates are scored against the secondary pool in C via process.cdist
# (multithreaded), one block at a time so the score matrix stays small.
_CHUNK = 2000


def _name_tokens(normalised_name: str) -> set[str]:
    """Tokens (length > 1) of an already-normalised name, deduplicated."""
    return {t for t in normalised_name.split() if len(t) > 1}


def fuzzy_key(
    candidates: list[ContactRecord],
    secondary: list[ContactRecord],
) -> dict[int, tuple[ContactRecord, int]]:
    """Confidence: name AND company each fuzzy-match independently.

    Scoring the concatenated 'name|company' key as one string lets a long
    shared company name drag the overall score above threshold even when the
    names share nothing. Comparing the two parts separately, with their own
    cutoffs, prevents that.

    The name gate (the strict one) is computed exactly as token_set_ratio but
    without scoring every pair. token_set_ratio >= token_sort_ratio always, and
    the only pairs where token_set clears the cutoff while token_sort does not
    are subset-name cases ("John Smith" vs "John Michael Smith"), which by
    construction share an exact token. So the survivor set is reconstructed from:

      1. a cheap vectorised token_sort_ratio cdist at the cutoff (a lower bound:
         every hit is a real token_set hit), plus
      2. the token-sharing pairs found through an inverted token index,

    and the exact token_set_ratio is then applied only to that sparse union. The
    result is bit-identical to scoring token_set_ratio over the full grid.
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

    # Inverted index over secondary name tokens, built once. Used to recover the
    # subset-name matches that the token_sort lower bound misses.
    token_to_cols: dict[str, list[int]] = defaultdict(list)
    for col, name in enumerate(sec_names):
        for tok in _name_tokens(name):
            token_to_cols[tok].append(col)

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

    # Stage 1: token_sort_ratio is a lower bound for token_set_ratio, so every
    # pair clearing the cutoff here is a guaranteed token_set survivor.
    sort_survivors: list[set[int]] = [set() for _ in q_names]
    for start in range(0, len(q_names), _CHUNK):
        block = q_names[start:start + _CHUNK]
        scores = process.cdist(
            block, sec_names,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=NAME_THRESHOLD,
            dtype=np.float64,
            workers=-1,
        )
        for bi, row in enumerate(scores):
            cols = np.nonzero(row)[0]
            if cols.size:
                sort_survivors[start + bi].update(int(c) for c in cols)

    matches: dict[int, tuple[ContactRecord, int]] = {}
    for qi, q_name in enumerate(q_names):
        # Stage 2: add the token-sharing secondaries (the only place a subset
        # match the lower bound missed can hide). The exact token_set_ratio gate
        # below filters this superset back down to the true survivor set.
        cols = set(sort_survivors[qi])
        for tok in _name_tokens(q_name):
            cols.update(token_to_cols.get(tok, ()))
        if not cols:
            continue

        q_company = q_companies[qi]
        best_record: ContactRecord | None = None
        best_score = 0
        for col in sorted(cols):  # ascending == original secondary order
            name_score = fuzz.token_set_ratio(q_name, sec_names[col])
            if name_score < NAME_THRESHOLD:
                continue
            company_score = fuzz.token_set_ratio(q_company, sec_companies[col])
            if company_score < COMPANY_THRESHOLD:
                continue
            # Mean is more forgiving than min; min is more conservative. Mean
            # surfaces "both pretty good" as a high confidence; min would
            # report a 99/85 match as 85.
            combined = (name_score + company_score) // 2
            if combined > best_score:
                best_score = combined
                best_record = sec_records[col]
        if best_record is not None:
            matches[cand_idx[qi]] = (best_record, best_score)
    return matches
