"""Runs dedup strategies against a primary sheet and a secondary pool.

Strategies are plain values (the Strategy dataclass), not subclasses.
The public entry point is deduplicate().
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..model import ContactField, ContactRecord, SheetData
from . import strategies


@dataclass(frozen=True, slots=True)
class RemovedRecord:
    record: ContactRecord
    matched: ContactRecord  # the secondary record that triggered the removal
    reason: str  # strategy label, e.g. "Exact email"
    confidence: int  # 0-100; 100 = exact match


@dataclass(frozen=True, slots=True)
class DedupResult:
    """Candidates that survived deduplication and those that were removed, with reasons."""

    kept: list[ContactRecord]
    removed: list[RemovedRecord]


@dataclass(frozen=True, slots=True)
class Strategy:
    """One dedup strategy. Holds a display label, the fields a sheet must
    provide before this strategy can run, and the matching function itself."""

    label: str
    required_fields: frozenset[ContactField]
    apply: Callable[
        [list[ContactRecord], list[ContactRecord]],
        # (matches: dict[idx -> (matched_secondary, confidence)])
        dict[int, tuple[ContactRecord, int]],
    ]


# Strategies trusted enough that a matched candidate can seed the secondary
# pool for later transitive passes. Fuzzy_name is excluded because its false
# positives would cascade through those passes.
SEEDING_STRATEGY_LABELS = frozenset({
    "Exact email",
    "Email username",
    "Name and company",
    "Fuzzy key",
})


def default_pipeline() -> list[Strategy]:
    """The five-strategy default pipeline, in order. Order matters: earlier strategies
    take precedence and their matches are not re-examined by later ones.
    Records are canonicalised at ContactRecord construction (email lowercased, whitespace collapsed)."""
    return [
        Strategy("Exact email", frozenset({ContactField.EMAIL}), strategies.exact_email),
        Strategy("Email username", frozenset({ContactField.EMAIL}), strategies.email_username),
        Strategy("Name and company", frozenset({ContactField.COMPANY}), strategies.name_company_key),
        Strategy("Fuzzy key", frozenset({ContactField.COMPANY}), strategies.fuzzy_key),
        Strategy("Fuzzy name", frozenset(), strategies.fuzzy_name),
    ]


def _run_pipeline_pass(
    pass_num: int,
    unmatched: list[ContactRecord],
    secondary: list[ContactRecord],
    available_fields: frozenset[ContactField],
    removed: list[RemovedRecord],
) -> tuple[list[ContactRecord], list[ContactRecord]]:
    """Run every applicable strategy against 'secondary' in order, labelling
    each removal 'Pass <n> <strategy.label>'. Returns the still-unmatched
    candidates and the newly removed records that qualify as seeds for the
    next transitive pass."""
    new_seeds: list[ContactRecord] = []
    for strategy in default_pipeline():
        if not strategy.required_fields <= available_fields:
            continue
        matches = strategy.apply(unmatched, secondary)
        if not matches:
            continue
        is_seeding = strategy.label in SEEDING_STRATEGY_LABELS  # only high-precision strategies contribute seeds
        survivors: list[ContactRecord] = []
        for i, record in enumerate(unmatched):
            match = matches.get(i)
            if match is None:
                survivors.append(record)
                continue
            matched_secondary, confidence = match
            removed.append(
                RemovedRecord(
                    record=record,
                    matched=matched_secondary,
                    reason=f"Pass {pass_num} {strategy.label}",
                    confidence=confidence,
                )
            )
            if is_seeding:
                new_seeds.append(record)
        unmatched = survivors
        if not unmatched:
            break
    return unmatched, new_seeds


def deduplicate(primary: SheetData, secondary: list[ContactRecord]) -> DedupResult:
    """Run the default pipeline, then keep iterating transitive passes until
    no new matches are found or no candidates remain. In each transitive pass,
    the secondary pool is the records matched by high-precision strategies in
    the previous pass. Strategies whose 'required_fields' are absent from the
    sheet are skipped. Each removal's 'reason' is labelled 'Pass <n> <strategy>'
    so the output can be sorted by pass."""

    unmatched: list[ContactRecord] = list(primary.records)
    removed: list[RemovedRecord] = []

    pass_num = 1
    unmatched, seeds = _run_pipeline_pass(
        pass_num, unmatched, secondary, primary.available_fields, removed,
    )

    # Each transitive pass uses only the seeds from the previous pass.
    # Survivors have already been tested against older pools, so there is
    # nothing to gain from repeating those comparisons.
    while unmatched and seeds:
        pass_num += 1
        unmatched, seeds = _run_pipeline_pass(
            pass_num, unmatched, seeds, primary.available_fields, removed,
        )

    return DedupResult(kept=unmatched, removed=removed)
    