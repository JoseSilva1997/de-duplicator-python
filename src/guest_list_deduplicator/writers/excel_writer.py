"""Writes the two output workbooks. Stateless function, no class wrapper.

In production resolves the user's Desktop. In dev (running from a source
checkout) resolves to <project>/outputs/ instead.
"""
from __future__ import annotations

from pathlib import Path

from ..dedup import DedupResult


def write(primary_path: Path, results: dict[str, DedupResult]) -> Path:
    """Write 'Updated guests list from <name>.xlsx' and (if anything was
    removed) 'People removed from <name>.xlsx' to the output directory.

    Returns the output directory.
    """
    raise NotImplementedError
