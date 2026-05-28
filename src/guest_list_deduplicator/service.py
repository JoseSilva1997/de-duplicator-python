"""Top-level dedup service. Module-level functions, no class wrapper.

These are the entry points the GUI calls. Implementations are stubs for now;
fill them in once the reader / orchestrator / writer modules are ready.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .settings import UserSettings


@dataclass(frozen=True, slots=True)
class Summary:
    sheets_processed: int
    total_kept: int
    total_removed: int
    no_email_dropped: int
    output_directory: Path


def list_sheets(file: Path) -> list[str]:
    """Sheet names in declaration order, hidden sheets excluded.

    CSV files always return a single synthetic sheet named after the file.
    """
    raise NotImplementedError


def count_records(file: Path, sheet_selection: list[str]) -> int:
    """Total record count across the selected sheets after read + mapper filter."""
    raise NotImplementedError


def run(
    primary_path: Path,
    primary_sheet_selection: list[str],
    secondary_path: Path,
    secondary_sheet_selection: list[str],
    settings: UserSettings,
) -> Summary:
    """Read both files, dedup each primary sheet against the combined secondary
    pool, write output workbooks, and return a Summary for the GUI."""
    raise NotImplementedError
