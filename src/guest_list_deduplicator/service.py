"""Top-level dedup service. The entry points the GUI calls.

`list_sheets` and `count_records` are wired through the readers package.
`run` is still a stub pending the dedup orchestrator and Excel writer.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from guest_list_deduplicator.dedup.orchestrator import DedupResult, deduplicate
from guest_list_deduplicator.model.sheet_data import SheetData
from .model import ContactRecord

from . import readers
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
    return readers.list_sheets(file)


def count_records(file: Path, sheet_selection: list[str]) -> int:
    """Total record count across the selected sheets after read + mapper filter."""
    sheets = readers.read(file, sheet_selection)
    return sum(len(s.records) for s in sheets.values())


def run(
    primary_path: Path,
    primary_sheet_selection: list[str],
    secondary_path: Path,
    secondary_sheet_selection: list[str],
    settings: UserSettings,
) -> Summary:
    """Read both files, dedup each primary sheet against the combined secondary
    pool, write outputs, return a Summary for the GUI."""
    # Read first — both sides — so any IO error surfaces before we do any work.
    primary_sheets = readers.read(primary_path, primary_sheet_selection)
    secondary_sheets = readers.read(secondary_path, secondary_sheet_selection)

    primary_rows_before = sum(len(sd.records) for sd in primary_sheets.values())

    # Optional pre-filtering step to drop records without an email address.
    no_email_dropped = 0
    if settings.drop_rows_without_email:
        primary_sheets = _require_email(primary_sheets)
        primary_rows_after = sum(len(sd.records) for sd in primary_sheets.values())
        no_email_dropped = primary_rows_before - primary_rows_after
    
    # All selected secondary sheets become one combined pool. Each primary sheet
    # is deduped against the full pool, not just same-named secondary sheets.
    secondary_pool: list[ContactRecord] = [
        record for sd in secondary_sheets.values() for record in sd.records]
    
    results: dict[str, DedupResult] = {}
    total_kept = 0
    total_removed = 0
    for name, sheet_data in primary_sheets.items():
        result = deduplicate(sheet_data, secondary_pool)
        results[name] = result
        total_kept += len(result.kept)
        total_removed += len(result.removed)

    # Writer is still stubbed. Placeholder lets you test the rest end-to-end.
    # output_dir = writer.write(primary_path, results)
    output_dir = Path(".")

    return Summary(
        sheets_processed=len(primary_sheets),
        total_kept=total_kept,
        total_removed=total_removed,
        no_email_dropped=no_email_dropped,
        output_directory=output_dir,
    )

def _require_email(sheets: dict[str, SheetData]) -> dict[str, SheetData]:
    """Return a new map with records lacking an email filtered out. Preserves
    sheet order and each sheet's available_fields (the column still exists
    even if every cell happens to be blank after filtering)."""
    return {
        name: SheetData(
            records=[r for r in sd.records if r.email is not None],
            available_fields=sd.available_fields,
        )
        for name, sd in sheets.items()
    }