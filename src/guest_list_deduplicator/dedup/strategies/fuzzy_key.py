"""fuzzy_key strategy: match candidates against secondary records using separate fuzzy
gates for name and company."""
from __future__ import annotations

from collections import defaultdict

import numpy as np
from rapidfuzz import fuzz, process

from ...model import ContactRecord
from .. import normalisation

NAME_THRESHOLD = 90  # tuned by spot check: high enough to avoid false positives, low enough not to miss obvious matches
COMPANY_THRESHOLD = 40  # lower than NAME_THRESHOLD because company names tend to be longer, so even small differences pull the ratio down more

# Candidates are scored against secondary in batches via process.cdist (multithreaded C).
# Batching keeps the intermediate score matrix from growing too large.
_CHUNK = 2000


def _name_tokens(normalised_name: str) -> set[str]:
    """Return the unique tokens from an already-normalised name, excluding single-character tokens.

    Single-character tokens (initials, stray punctuation artefacts) match too broadly
    and would flood the inverted index with noise.
    """
    return {t for t in normalised_name.split() if len(t) > 1}


def fuzzy_key(
    candidates: list[ContactRecord],
    secondary: list[ContactRecord],
) -> dict[int, tuple[ContactRecord, int]]:
    """Match candidates against secondary records, requiring both name and company to fuzzy-match.

    Scoring a concatenated "name|company" key as a single string is unreliable: a long shared
    company name can push the combined score above threshold even when the names share nothing.
    Comparing name and company separately, each against its own cutoff, prevents that.

    The name gate uses token_set_ratio semantics but avoids scoring every pair in the grid.
    token_set_ratio is always >= token_sort_ratio, and the only pairs where token_set clears
    the cutoff while token_sort does not are subset-name cases ("John Smith" vs "John Michael
    Smith"), which by construction share an exact token. The full survivor set is therefore
    built in two stages:

      1. A vectorised token_sort_ratio cdist pass at the cutoff. Every hit here is guaranteed
         to survive the token_set gate too (lower bound).
      2. An inverted token index lookup to catch the subset-name pairs the sort pass misses.

    The exact token_set_ratio is then applied only to that sparse union. The result is
    bit-identical to a full grid score.

    This avoids calling token_set_ratio across the full candidate × secondary grid.
    token_sort_ratio runs as vectorised, multithreaded C via process.cdist; token_set_ratio
    cannot be vectorised the same way. The two-stage design means the expensive scorer only
    runs on the small fraction of pairs that survive the cheap pass.
    """
    # Normalise secondary records up front and drop any that lack a name or company,
    # since those can't form a usable key.
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

    # Build an inverted index from name tokens to secondary column indices.
    # This lets stage 2 recover subset-name matches that the token_sort pass misses.
    token_to_cols: dict[str, list[int]] = defaultdict(list)
    for col, name in enumerate(sec_names):
        for tok in _name_tokens(name):
            token_to_cols[tok].append(col)

    # Normalise candidate records, tracking each one's original index in 'candidates'
    # so the result map can refer back to it. cand_idx[qi] gives the original position.
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

    # Stage 1: vectorised token_sort_ratio via process.cdist (multithreaded C, SIMD-friendly).
    # token_set_ratio involves set operations that can't be parallelised the same way, so
    # running it over the full grid would be far slower. token_sort_ratio serves as a cheap
    # lower bound: because token_sort_ratio <= token_set_ratio, every pair that passes here
    # is guaranteed to pass the token_set gate too.
    # sort_survivors[qi] is indexed by compressed position qi, parallel to cand_idx.
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
        # Stage 2: add any secondary records that share a name token with this candidate.
        # These are the only pairs the sort pass could have missed. The token_set_ratio
        # check below then filters the combined set down to genuine survivors.
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
            # Mean rewards pairs where both scores are good; min would cap a 99/85 match
            # at 85, hiding the strength of the name match. The floor division only affects
            # tie-breaking between multiple secondary matches.
            combined = (name_score + company_score) // 2
            if combined > best_score:
                best_score = combined
                best_record = sec_records[col]
        if best_record is not None:
            matches[cand_idx[qi]] = (best_record, best_score)
    return matches
