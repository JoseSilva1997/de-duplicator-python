from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterator

import numpy as np
from rapidfuzz import fuzz, process

from ...model import ContactRecord
from .. import normalisation

FIRST_NAME_THRESHOLD = 92 # token_set_ratio: lenient, handles initials and middle names
LAST_NAME_THRESHOLD = 90  # fuzz.ratio: strict, rejects "Couto" vs "Couto Silva"
FULLNAME_THRESHOLD = 100  # fallback when first/last aren't separately available

_CHUNK = 2000


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


def _blocks(
    queries: list[str],
    choices: list[str],
    scorer: Callable,
    cutoff: int,
) -> Iterator[tuple[int, int, float]]:
    """Yield (query_index, choice_index, score) for every pair whose score
    clears `cutoff`, computed in C via process.cdist one chunk of queries at a
    time. choice indices come back ascending (numpy nonzero order)."""
    for start in range(0, len(queries), _CHUNK):
        block = queries[start:start + _CHUNK]
        matrix = process.cdist(
            block, choices,
            scorer=scorer,
            score_cutoff=cutoff,
            dtype=np.float64,
            workers=-1,
        )
        for bi, row in enumerate(matrix):
            cols = np.nonzero(row)[0]  # scores >= cutoff; the rest were zeroed
            if cols.size == 0:
                continue
            qi = start + bi
            for c in cols:
                yield qi, int(c), float(row[c])


def fuzzy_name(
    candidates: list[ContactRecord],
    secondary: list[ContactRecord],
) -> dict[int, tuple[ContactRecord, int]]:
    """Confidence: first name AND last name each fuzzy-match independently, with a
    country veto. The catch-all strategy when no email or company match exists.

    Last names use fuzz.ratio (no subset bonus) so "Couto" doesn't collapse into
    "Couto Silva". First names use token_set_ratio to forgive middle names and
    initial variants. When the record only carries a full_name (no split), we fall
    back to whole-string token_set_ratio at an exact-match cutoff.

    The strict gate of each path (last-name ratio for split records, the exact
    full-name cutoff for the fallback) runs first as a vectorised process.cdist
    with score_cutoff, so only the sparse survivors get the per-pair country veto
    and first-name refinement. Survivors are folded in original secondary order,
    so the best-match tie-break is identical to a plain double loop.
    """
    sec_first: list[str | None] = []
    sec_last: list[str | None] = []
    sec_fullrep: list[str] = []
    sec_country: list[str | None] = []
    sec_record: list[ContactRecord] = []
    for r in secondary:
        first, last, full = _split_parts(r)
        if first is None and full is None:
            continue
        sec_first.append(first)
        sec_last.append(last)
        sec_fullrep.append(full if full is not None else f"{first} {last}")
        sec_country.append(_country_key(r))
        sec_record.append(r)

    if not sec_record:
        return {}

    split_cols = [k for k in range(len(sec_record)) if sec_first[k] is not None]
    fullonly_cols = [k for k in range(len(sec_record)) if sec_first[k] is None]

    # Partition candidates: split (first+last present) vs full-name-only.
    qsplit_idx: list[int] = []
    qsplit_first: list[str] = []
    qsplit_last: list[str] = []
    qsplit_fullrep: list[str] = []
    qsplit_country: list[str | None] = []
    qfull_idx: list[int] = []
    qfull_full: list[str] = []
    qfull_country: list[str | None] = []
    for i, candidate in enumerate(candidates):
        q_first, q_last, q_full = _split_parts(candidate)
        if q_first is None and q_full is None:
            continue
        country = _country_key(candidate)
        if q_first is not None:
            qsplit_idx.append(i)
            qsplit_first.append(q_first)
            qsplit_last.append(q_last)  # type: ignore[arg-type]
            qsplit_fullrep.append(f"{q_first} {q_last}")
            qsplit_country.append(country)
        else:
            qfull_idx.append(i)
            qfull_full.append(q_full)  # type: ignore[arg-type]
            qfull_country.append(country)

    # Per original candidate index: list of (secondary_col, combined, record).
    survivors: dict[int, list[tuple[int, float, ContactRecord]]] = defaultdict(list)

    # Path 1: split candidate vs split secondary. Block on last name (the strict
    # gate), then refine with the first-name threshold and country veto.
    if qsplit_last and split_cols:
        split_last_choices = [sec_last[k] for k in split_cols]
        for qi, ci, last_score in _blocks(qsplit_last, split_last_choices, fuzz.ratio, LAST_NAME_THRESHOLD):
            col = split_cols[ci]
            if _country_conflict(qsplit_country[qi], sec_country[col]):
                continue
            first_score = fuzz.token_set_ratio(qsplit_first[qi], sec_first[col])
            if first_score < FIRST_NAME_THRESHOLD:
                continue
            combined = (first_score + last_score) // 2
            survivors[qsplit_idx[qi]].append((col, combined, sec_record[col]))

    # Path 2: split candidate vs full-only secondary. The candidate's split can't
    # be paired part-by-part with a one-field full name, so both go through the
    # whole-string fallback at the exact cutoff.
    if qsplit_fullrep and fullonly_cols:
        fo_choices = [sec_fullrep[k] for k in fullonly_cols]
        for qi, ci, score in _blocks(qsplit_fullrep, fo_choices, fuzz.token_set_ratio, FULLNAME_THRESHOLD):
            col = fullonly_cols[ci]
            if _country_conflict(qsplit_country[qi], sec_country[col]):
                continue
            survivors[qsplit_idx[qi]].append((col, score, sec_record[col]))

    # Path 3: full-only candidate vs every secondary (using each secondary's
    # whole-string representation), whole-string fallback at the exact cutoff.
    if qfull_full:
        for qi, col, score in _blocks(qfull_full, sec_fullrep, fuzz.token_set_ratio, FULLNAME_THRESHOLD):
            if _country_conflict(qfull_country[qi], sec_country[col]):
                continue
            survivors[qfull_idx[qi]].append((col, score, sec_record[col]))

    matches: dict[int, tuple[ContactRecord, int]] = {}
    for cand_i, survs in survivors.items():
        best_record: ContactRecord | None = None
        best_score = 0
        for _col, combined, record in sorted(survs, key=lambda t: t[0]):
            if combined > best_score:
                best_score = combined
                best_record = record
        if best_record is not None:
            matches[cand_i] = (best_record, best_score)
    return matches
