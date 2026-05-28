"""Writes the two output workbooks. Stateless function, no class wrapper.

In production resolves the user's Desktop. In dev (running from a source
checkout) resolves to <project>/outputs/ instead.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys

from guest_list_deduplicator.model.contact_field import ContactField
import openpyxl
from ..model.sheet_data import SheetData

from ..dedup import DedupResult

# Order in which columns appear in the output. Anything not in this list is
# dropped from output entirely.
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
    """Write the two output workbooks. Returns the directory they were written
    to so the GUI can display it.

    `sheets` is the original primary read (needed for each sheet's
    available_fields); `results` is the per-sheet dedup outcome. Both maps
    share the same keys in the same order.
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

    # The "People removed" workbook is skipped entirely when nothing was
    # removed — no point producing an empty file the user has to delete.
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
    # openpyxl gives every new workbook a default "Sheet" that we'll replace.
    default_sheet = wb.active
    wb.remove(default_sheet)

    for name, sheet_data in sheets.items():
        result = results[name]
        # In the "removed" workbook, sheets that contributed no removals are
        # omitted entirely — matches the Java behaviour.
        records = result.removed if include_removed_columns else result.kept
        if include_removed_columns and not records:
            continue

        columns = _columns_for(sheet_data.available_fields)
        ws = wb.create_sheet(title=_safe_sheet_name(name))

        # Header row. RemovedRecord adds two trailing columns.
        header = [field.label for field in columns]
        if include_removed_columns:
            header += ["Reason", "Confidence"]
        ws.append(header)

        for entry in records:
            # entry is either a ContactRecord (kept) or a RemovedRecord (removed).
            record = entry.record if include_removed_columns else entry
            row = [_record_cell(record, field) for field in columns]
            if include_removed_columns:
                row += [entry.reason, entry.confidence]
            ws.append(row)

    wb.save(path)


def _columns_for(available: frozenset[ContactField]) -> list[ContactField]:
    """Pick the columns to write for this sheet, in canonical order."""
    columns = list(_DEFAULT_COLUMNS)
    # If first+last are both present, the full-name column is redundant.
    if ContactField.FIRST_NAME in available and ContactField.LAST_NAME in available:
        columns.remove(ContactField.FULL_NAME)
    # Country is pass-through only — skip the column entirely if the source
    # never had one. Avoids a column of blanks for the common case.
    if ContactField.COUNTRY not in available:
        columns.remove(ContactField.COUNTRY)
    return columns


def _safe_sheet_name(name: str) -> str:
    """Excel caps sheet names at 31 chars; truncate to fit."""
    return name[:31]


def _record_cell(record, field: ContactField) -> str:
    """Pull a single cell value out of a ContactRecord by field. Maps
    ContactField → the matching attribute name."""
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
    """Drops files in users desktop in production; <repo>/outputs in development.

    Dev detection: walk up from this file's location and check for a
    pyproject.toml at the repo root. Editable installs leave the source files
    in-tree, so this works whether the user is running via `python -m ...` or
    the installed `guest-list-dedup` script.
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