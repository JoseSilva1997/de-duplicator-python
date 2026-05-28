"""Map a row of header cells to {ContactField: column_index}.

Walks fields → aliases → header cells, so earlier aliases win over column order.
If both FIRST_NAME and LAST_NAME resolve, FULL_NAME is dropped from the map.
"""
from __future__ import annotations

from ..model import ContactField


def resolve(headers: list[str | None]) -> dict[ContactField, int]:
    raise NotImplementedError
