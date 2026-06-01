from __future__ import annotations

from dataclasses import dataclass

from .contact_field import ContactField
from .contact_record import ContactRecord


@dataclass(frozen=True, slots=True)
class SheetData:
    """Parsed contents of a single sheet: the ContactRecord rows and the set of
    ContactField columns that were present in the source file."""

    records: list[ContactRecord]
    available_fields: frozenset[ContactField]
