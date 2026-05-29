"""Runs all dedup strategies against a primary sheet and a secondary pool.

Strategies are values (Strategy dataclass) rather than classes, and the
public entry point is a single function — `deduplicate()`.
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
    confidence: int  # 0-100


@dataclass(frozen=True, slots=True)
class DedupResult:
    kept: list[ContactRecord]
    removed: list[RemovedRecord]


@dataclass(frozen=True, slots=True)
class Strategy:
    """A dedup strategy: a label, a required-field set checked at sheet level,
    and a function that returns matches for the still-unmatched candidates."""

    label: str
    required_fields: frozenset[ContactField]
    apply: Callable[
        [list[ContactRecord], list[ContactRecord]],
        # (matches: dict[idx -> (matched_secondary, confidence)])
        dict[int, tuple[ContactRecord, int]],
    ]


# Strategies precise enough that a candidate they match can itself act as an
# identity anchor in later transitive passes. Fuzzy_name is deliberately
# excluded: seeding from it would cascade its false positives.
SEEDING_STRATEGY_LABELS = frozenset({
    "Exact email",
    "Email username",
    "Name and company",
    "Fuzzy key",
})


def default_pipeline() -> list[Strategy]:
    """The five-strategy default pipeline, in order."""
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
    """Run every applicable strategy once against `secondary`, tagging each
    removal with `"Pass <n> <strategy.label>"`. Returns the new unmatched list
    and the candidates removed by high-precision strategies (the seeds usable
    for the next transitive pass)."""
    new_seeds: list[ContactRecord] = []
    for strategy in default_pipeline():
        if not strategy.required_fields <= available_fields:
            continue
        matches = strategy.apply(unmatched, secondary)
        if not matches:
            continue
        is_seeding = strategy.label in SEEDING_STRATEGY_LABELS
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
    """Run the default pipeline against `secondary`, then iterate transitive
    passes where the secondary pool is the candidates matched by high-precision
    strategies in the previous pass. Strategies whose required_fields aren't
    present on the sheet are skipped entirely. Removal `reason` is labelled
    `"Pass <n> <strategy>"` so output sorts by pass."""

    unmatched: list[ContactRecord] = list(primary.records)
    removed: list[RemovedRecord] = []

    pass_num = 1
    unmatched, seeds = _run_pipeline_pass(
        pass_num, unmatched, secondary, primary.available_fields, removed,
    )

    # Transitive reconciliation. Each pass uses only the seeds produced by the
    # previous pass — the survivors have already been tested against everything
    # earlier, so re-checking against older pools would do no new work.
    while unmatched and seeds:
        pass_num += 1
        unmatched, seeds = _run_pipeline_pass(
            pass_num, unmatched, seeds, primary.available_fields, removed,
        )

    return DedupResult(kept=unmatched, removed=removed)
    