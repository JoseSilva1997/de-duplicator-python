"""Maps a row of header cells to {ContactField: column_index}.

For each ContactField, aliases are tried in order and the first match wins.
If both FIRST_NAME and LAST_NAME are found, FULL_NAME is dropped from the result
because split names are more precise and combining them would be redundant.
"""
from __future__ import annotations

from ..model import ContactField
import re

_HEADER_CLEAN = re.compile(r"[^a-z0-9]")  # strips spaces, underscores, and punctuation before alias matching

def _normalise_header(cell: str | None) -> str:
    """Lowercase and strip non-alphanumeric characters so variants like
    'First Name', 'first_name', and 'firstname' all produce the same token.
    """
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
            break  # stop at the first matching alias; alias list order is the priority signal
    if ContactField.FIRST_NAME in result and ContactField.LAST_NAME in result:
        result.pop(ContactField.FULL_NAME, None)  # split names are more reliable; prefer them over FULL_NAME
    return result
    


