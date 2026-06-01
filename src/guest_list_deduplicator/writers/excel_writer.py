"""Writes the two output workbooks. Saves to the user's Desktop when running normally,
or to <project>/outputs/ during development.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys

from guest_list_deduplicator.model.contact_field import ContactField
import openpyxl
from ..model.sheet_data import SheetData

from ..dedup import DedupResult

# Columns that appear in the output, in this order. Any column not listed here is left out.
_DEFAULT_COLUMNS: tuple[ContactField, ...] = (
    ContactField.FIRST_NAME,
    ContactField.LAST_NAME,
    ContactField.FULL_NAME,
    ContactField.EMAIL,
    ContactField.COMPANY,
    ContactField.JOB_TITLE,
    ContactField.COUNTRY,
)


def write(
    primary_path: Path,
    sheets: dict[str, SheetData],
    results: dict[str, DedupResult],
) -> Path:
    """Write the two output workbooks. Returns the directory they were saved to
    so the GUI can open it.

    `sheets` carries the original input for each tab (needed to know which columns
    were present); `results` holds what was kept and removed. Both share the same keys.
    """
    output_dir = _resolve_output_dir()
    base = primary_path.stem

    kept_path = output_dir / f"Updated guests list from {base}.xlsx"
    _write_workbook(
        kept_path,
        sheets,
        results,
        include_removed_columns=False,
    )

    # Only write the "People removed" file if something was actually removed --
    # no point leaving an empty file on the user's Desktop.
    if any(result.removed for result in results.values()):
        removed_path = output_dir / f"People removed from {base}.xlsx"
        _write_workbook(
            removed_path,
            sheets,
            results,
            include_removed_columns=True,
        )

    return output_dir

def _write_workbook(
    path: Path,
    sheets: dict[str, SheetData],
    results: dict[str, DedupResult],
    *,
    include_removed_columns: bool,
) -> None:
    wb = openpyxl.Workbook()
    # openpyxl always creates a placeholder sheet; remove it before adding our own.
    default_sheet = wb.active
    wb.remove(default_sheet)

    for name, sheet_data in sheets.items():
        result = results[name]
        # In the "removed" workbook, skip any tab where nothing was removed.
        records = result.removed if include_removed_columns else result.kept
        if include_removed_columns and not records:
            continue

        columns = _columns_for(sheet_data.available_fields)
        ws = wb.create_sheet(title=_safe_sheet_name(name))

        # For RemovedRecord rows, add extra columns showing why the row was removed and which attendee it matched.
        header = [field.label for field in columns]
        if include_removed_columns:
            header += ["Reason", "Confidence", "", "Matched name", "Matched email", "Matched company"]
        ws.append(header)

        for entry in records:
            record = entry.record if include_removed_columns else entry
            row = [_record_cell(record, field) for field in columns]
            if include_removed_columns:
                matched = entry.matched
                row += [
                    entry.reason,
                    entry.confidence,
                    "",
                    matched.resolved_full_name() or "",
                    matched.email or "",
                    matched.company or "",
                ]
            ws.append(row)

    wb.save(path)


def _columns_for(available: frozenset[ContactField]) -> list[ContactField]:
    """Returns the columns to write for this sheet, in the standard order."""
    columns = list(_DEFAULT_COLUMNS)
    # If both first and last name are present, the combined full-name column adds nothing.
    if ContactField.FIRST_NAME in available and ContactField.LAST_NAME in available:
        columns.remove(ContactField.FULL_NAME)
    # Only include a country column if the source data had one; otherwise it would just be a column of blanks.
    if ContactField.COUNTRY not in available:
        columns.remove(ContactField.COUNTRY)
    return columns


def _safe_sheet_name(name: str) -> str:
    """Excel sheet names have a 31-character limit; truncate to fit."""
    return name[:31]


def _record_cell(record, field: ContactField) -> str:
    """Gets the value for a given ContactField from a ContactRecord."""
    attr = {
        ContactField.FIRST_NAME: "first_name",
        ContactField.LAST_NAME: "last_name",
        ContactField.FULL_NAME: "full_name",
        ContactField.EMAIL: "email",
        ContactField.COMPANY: "company",
        ContactField.JOB_TITLE: "job_title",
        ContactField.COUNTRY: "country",
    }[field]
    value = getattr(record, attr)
    return value if value is not None else ""


def _resolve_output_dir() -> Path:
    """Returns the folder where output files are saved. Uses the user's Desktop in
    normal use, or a local outputs/ folder during development (detected by the
    presence of pyproject.toml in the repo root).
    """
    if not getattr(sys, "frozen", False):
        candidate_root = Path(__file__).resolve().parents[3]
        if (candidate_root / "pyproject.toml").exists():
            dev_dir = candidate_root / "outputs"
            dev_dir.mkdir(exist_ok=True)
            return dev_dir
    profile = Path(os.environ.get("USERPROFILE", str(Path.home())))
    desktop = profile / "Desktop"
    return desktop if desktop.exists() else profile