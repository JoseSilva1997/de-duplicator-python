from __future__ import annotations

from dataclasses import dataclass

from .contact_field import ContactField
from .contact_record import ContactRecord


@dataclass(frozen=True, slots=True)
class SheetData:
    records: list[ContactRecord]
    available_fields: frozenset[ContactField]
