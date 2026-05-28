"""Map a row of header cells to {ContactField: column_index}.

Walks fields → aliases → header cells, so earlier aliases win over column order.
If both FIRST_NAME and LAST_NAME resolve, FULL_NAME is dropped from the map.
"""
from __future__ import annotations

from ..model import ContactField
import re

_HEADER_CLEAN = re.compile(r"[^a-z0-9]")

def _normalise_header(cell: str | None) -> str:
    if cell is None:
        return ""
    return _HEADER_CLEAN.sub("", cell.lower())


def resolve(headers: list[str | None]) -> dict[ContactField, int]:
    normalised = [_normalise_header(h) for h in headers]
    result: dict[ContactField, int] = {}
    for field in ContactField:
        for alias in field.aliases:
            try:
                idx = normalised.index(alias)
            except ValueError:
                continue
            result[field] = idx
            break # alias order wins: stop at first match for this field
    if ContactField.FIRST_NAME in result and ContactField.LAST_NAME in result:
        result.pop(ContactField.FULL_NAME, None) # drop FULL_NAME if FIRST_NAME and LAST_NAME are both present
    return result
    


