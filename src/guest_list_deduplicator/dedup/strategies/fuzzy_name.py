from __future__ import annotations

from ...model import ContactRecord
from rapidfuzz import process, fuzz
from .. import normalisation

CUTOFF_THRESHOLD = 100 # 100 = exact match, but with normalisation applied.
def fuzzy_name(
    candidates: list[ContactRecord],
    secondary: list[ContactRecord],
) -> dict[int, tuple[ContactRecord, int]]:
    """Per-match confidence ≥ CUTOFF_THRESHOLD: fuzzy token-set match on the resolved name
    alone. The catch-all strategy when no email or company match exists."""
    # Pre-normalise the secondary names. Records without a usable name are
    # dropped here so extractOne never sees them.
    secondary_names: list[str] = []
    secondary_records: list[ContactRecord] = []
    for record in secondary:
        name = record.resolved_full_name()
        if name is not None:
            secondary_names.append(normalisation.normalise_string(name))
            secondary_records.append(record)

    # Nothing to match against, e.g. the secondary side has no records with
    # a usable name. Skip the work entirely.
    if not secondary_names:
        return {}

    matches: dict[int, tuple[ContactRecord, int]] = {}
    for i, candidate in enumerate(candidates):
        name = candidate.resolved_full_name()
        if name is None:
            continue
        query = normalisation.normalise_string(name)
        # extractOne returns (matched_string, score, index_in_choices) or None
        # if nothing crossed the score_cutoff.
        result = process.extractOne(
            query,
            secondary_names,
            scorer=fuzz.token_set_ratio,
            score_cutoff=CUTOFF_THRESHOLD,
            processor=None, # names are already normalised; don't do it again
        )
        if result is not None:
            _, score, idx = result
            matches[i] = (secondary_records[idx], int(score))
    return matches