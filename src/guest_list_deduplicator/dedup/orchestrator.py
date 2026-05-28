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


def default_pipeline() -> list[Strategy]:
    """The five-strategy default pipeline, in order."""
    return [
        Strategy("Exact email", frozenset({ContactField.EMAIL}), strategies.exact_email),
        Strategy("Email username", frozenset({ContactField.EMAIL}), strategies.email_username),
        Strategy("Name and company", frozenset({ContactField.COMPANY}), strategies.name_company_key),
        Strategy("Fuzzy key", frozenset({ContactField.COMPANY}), strategies.fuzzy_key),
        Strategy("Fuzzy name", frozenset(), strategies.fuzzy_name),
    ]


def deduplicate(primary: SheetData, secondary: list[ContactRecord]) -> DedupResult:
    """Run the default pipeline. Each strategy sees only the candidates that
    survived the previous strategies. Strategies whose required_fields aren't
    all present on the sheet are skipped entirely."""

    # Working list of candidates that haven't been matched yet. Starts as the
    # full sheet and shrinks after each strategy pass.
    unmatched: list[ContactRecord] = list(primary.records)
    removed: list[RemovedRecord] = []

    for strategy in default_pipeline():
        # Sheet-level gate: skip strategies whose required columns aren't even
        # present in the source. Per-row null checks live inside the strategies
        # themselves (a sheet can have an EMAIL column with blank cells).
        if not strategy.required_fields <= primary.available_fields:
            continue

        matches = strategy.apply(unmatched, secondary)
        if not matches:
            continue

        # Split `unmatched` into "matched this round" (records removed) and "still
        # unmatched" (for the next strategy). 
        # Iterating with enumerate keeps the mapping from index → record straight.
        survivors: list[ContactRecord] = []
        for i, record in enumerate(unmatched):
            match = matches.get(i)
            if match is None:
                survivors.append(record)
            else:
                matched_secondary, confidence = match
                removed.append(
                    RemovedRecord(
                        record=record,
                        matched=matched_secondary,
                        reason=strategy.label,
                        confidence=confidence,
                    )
                )
        unmatched = survivors

        # Tiny perf shortcut: if every candidate has been matched, no later
        # strategy has anything to do.
        if not unmatched:
            break
    
    return DedupResult(kept=unmatched, removed=removed)
    