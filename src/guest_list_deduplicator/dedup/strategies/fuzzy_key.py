from __future__ import annotations

from ...model import ContactRecord
from rapidfuzz import process, fuzz
from .. import normalisation

CUTOFF_THRESHOLD = 85 # good balance of false positives vs missed matches, based on spot checks

def fuzzy_key(
    candidates: list[ContactRecord],
    secondary: list[ContactRecord],
) -> dict[int, tuple[ContactRecord, int]]:
    """Confidence 85: fuzzy token-set match on the name|company key."""
    # Pre-compute the keys for every secondary record once. Parallel lists let
    # us recover the original record from extractOne's returned index.
    secondary_keys: list[str] = []
    secondary_records: list[ContactRecord] = []
    for record in secondary:
        key = normalisation.key_for(record)
        if key is not None:
            secondary_keys.append(key)
            secondary_records.append(record)
    
    # Nothing to match against, e.g. the secondary side has no records with
    # both a name and a company. Skip the work entirely.
    if not secondary_keys:
        return {}

    matches: dict[int, tuple[ContactRecord, int]] = {}
    for i, candidate in enumerate(candidates):
        query = normalisation.key_for(candidate)
        if query is None:
            continue
        # extractOne returns (matched_string, score, index_in_choices) or None
        # if nothing crossed the score_cutoff.
        result = process.extractOne(
            query,
            secondary_keys,
            scorer=fuzz.token_set_ratio,
            score_cutoff=CUTOFF_THRESHOLD,
            processor=None, # keys are already normalised; don't do it again
        )
        if result is not None:
            _, score, idx = result
            matches[i] = (secondary_records[idx], int(score))
    return matches