"""Top-level service layer. These are the entry points the GUI calls.

'list_sheets' and 'count_records' delegate to the readers package.
'run' reads both files, runs the dedup pipeline, and writes the output.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from guest_list_deduplicator.dedup.orchestrator import DedupResult, deduplicate
from guest_list_deduplicator.model.sheet_data import SheetData
from .model import ContactRecord
from .writers import write as write_outputs

from . import readers
from .settings import UserSettings


@dataclass(frozen=True, slots=True)
class Summary:
    """Aggregated counts returned by 'run', used to populate the GUI result panel.

    'no_email_dropped' counts records discarded by the pre-filter (missing email),
    which is separate from 'total_removed' (records matched as duplicates).
    """
    sheets_processed: int
    total_kept: int
    total_removed: int
    no_email_dropped: int
    output_directory: Path


def list_sheets(file: Path) -> list[str]:
    """Returns sheet names in declaration order, with hidden sheets excluded.

    CSV files always return a single synthetic sheet named after the file.
    """
    return readers.list_sheets(file)


def count_records(file: Path, sheet_selection: list[str]) -> int:
    """Returns the total number of records across the selected sheets, after reading and applying column mapping."""
    sheets = readers.read(file, sheet_selection)
    return sum(len(s.records) for s in sheets.values())


def run(
    primary_path: Path,
    primary_sheet_selection: list[str],
    secondary_path: Path,
    secondary_sheet_selection: list[str],
    settings: UserSettings,
) -> Summary:
    """Read both files, deduplicate each primary sheet against the combined secondary pool, write the outputs, and return a Summary for the GUI."""
    # Read both files upfront so any IO error surfaces before any processing begins.
    primary_sheets = readers.read(primary_path, primary_sheet_selection)
    secondary_sheets = readers.read(secondary_path, secondary_sheet_selection)

    primary_rows_before = sum(len(sd.records) for sd in primary_sheets.values())

    # Optional pre-filtering step to drop records without an email address.
    no_email_dropped = 0
    if settings.drop_rows_without_email:
        primary_sheets = _require_email(primary_sheets)
        primary_rows_after = sum(len(sd.records) for sd in primary_sheets.values())
        no_email_dropped = primary_rows_before - primary_rows_after
    
    # Merge all selected secondary sheets into one pool. Each primary sheet
    # is checked against the full pool, not just sheets with matching names.
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

    output_dir = write_outputs(primary_path, primary_sheets, results)

    return Summary(
        sheets_processed=len(primary_sheets),
        total_kept=total_kept,
        total_removed=total_removed,
        no_email_dropped=no_email_dropped,
        output_directory=output_dir,
    )

def _require_email(sheets: dict[str, SheetData]) -> dict[str, SheetData]:
    """Returns a copy of the sheet map with records missing an email removed.

    Sheet order is preserved. Each sheet's 'available_fields' is kept intact: the column
    remains listed even if all its cells are blank after filtering.
    """
    return {
        name: SheetData(
            records=[r for r in sd.records if r.email is not None],
            available_fields=sd.available_fields,
        )
        for name, sd in sheets.items()
    }