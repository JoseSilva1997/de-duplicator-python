"""Runs all dedup strategies against a primary sheet and a secondary pool.

The Java code wraps this in a DedupOrchestrator class; in Python it's just
deduplicate(). Strategies are values (Strategy dataclass) rather than classes.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..model import ContactField, ContactRecord, SheetData
from . import strategies


@dataclass(frozen=True, slots=True)
class RemovedRecord:
    record: ContactRecord
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


def deduplicate(primary: SheetData, secondary_pool: list[ContactRecord]) -> DedupResult:
    """Run the default pipeline. Each strategy sees only still-unmatched
    primary records; strategies whose required_fields aren't all available on
    the sheet are skipped."""
    raise NotImplementedError
