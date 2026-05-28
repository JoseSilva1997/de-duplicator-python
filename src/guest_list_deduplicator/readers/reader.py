"""Reads `.csv`, `.xlsx`, and `.xls` files into {sheet_name: SheetData}.

The public entry points (`list_sheets`, `read`) switch on the file suffix and
delegate to per-format helpers. The shared `_rows_to_sheet` helper finds the
header row (skipping any leading blank or title rows) and maps the remaining
rows into `ContactRecord`s, dropping any row that fails `has_identifier()`.
"""
from __future__ import annotations

from pathlib import Path

from ..model import SheetData, ContactRecord, ContactField
from . import header_resolver
import csv
import openpyxl
import xlrd

def list_sheets(path: Path) -> list[str]:
    """Return visible sheet names. CSV → single synthetic sheet named after the file."""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _list_sheets_csv(path)
    elif suffix == ".xlsx":
        return _list_sheets_xlsx(path)
    elif suffix == ".xls":
        return _list_sheets_xls(path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")


def read(path: Path, sheet_selection: list[str]) -> dict[str, SheetData]:
    """Read selected sheets into a {sheet_name: SheetData} map preserving order.

    Headers are resolved via header_resolver. Rows failing
    ContactRecord.has_identifier() are dropped during mapping.
    """
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_csv(path)
    elif suffix == ".xlsx":
        return _read_xlsx(path, sheet_selection)
    elif suffix == ".xls":
        return _read_xls(path, sheet_selection)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")


def _list_sheets_csv(path: Path) -> list[str]:
    return [path.stem]


def _read_csv(path: Path) -> dict[str, SheetData]:
    # utf-8-sig silently strips the BOM that Excel-exported CSVs often start with;
    # without it the first header cell would contain ﻿ and miss every alias.
    sheet_name = path.stem
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    return {sheet_name: _rows_to_sheet(rows)}


def _list_sheets_xlsx(path: Path) -> list[str]:
    # read_only streams the file instead of loading it into memory; data_only
    # returns formula cells' cached values instead of the formula text itself.
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        return [name for name in wb.sheetnames if wb[name].sheet_state == "visible"]
    finally:
        wb.close()


def _read_xlsx(path: Path, sheet_selection: list[str]) -> dict[str, SheetData]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        result: dict[str, SheetData] = {}
        for name in sheet_selection:
            ws = wb[name]
            rows = [[_cell_to_str(c) for c in row] for row in ws.iter_rows(values_only=True)]
            result[name] = _rows_to_sheet(rows)
        return result
    finally:
        wb.close()


def _list_sheets_xls(path: Path) -> list[str]:
    wb = xlrd.open_workbook(str(path), on_demand=True)
    return [
        wb.sheet_names()[i]
        for i in range(wb.nsheets)
        if wb.sheet_by_index(i).visibility == 0 # xlrd defines 0 as visible
    ]


def _read_xls(path: Path, sheet_selection: list[str]) -> dict[str, SheetData]:
    wb = xlrd.open_workbook(str(path))
    result: dict[str, SheetData] = {}
    for name in sheet_selection:
        sheet = wb.sheet_by_name(name)
        rows = [
            [_cell_to_str(sheet.cell_value(r, c)) for c in range(sheet.ncols)]
            for r in range(sheet.nrows)
        ]
        result[name] = _rows_to_sheet(rows)
    return result


def _cell_to_str(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _rows_to_sheet(rows: list[list[str]]) -> SheetData:
    # Walk down from the top until a row produces a non-empty field map. 
    # This skips leading blank rows and title rows whose cells don't match 
    # any ContactField alias.
    field_map: dict[ContactField, int] = {}
    data_start = 0
    for i, row in enumerate(rows):
        field_map = header_resolver.resolve(row)
        if field_map:
            data_start = i + 1
            break
    records = []

    for row in rows[data_start:]:
        record = _row_to_record(row, field_map)
        if record is not None:
            records.append(record)

    return SheetData(records=records, available_fields=frozenset(field_map.keys()))


def _row_to_record(
        cells: list[str | None],
        field_map: dict[ContactField, int],
) -> ContactRecord | None:
    def get(field: ContactField) -> str | None:
        # idx >= len(cells) guards against ragged CSV rows: short rows would
        # otherwise IndexError when a trailing column is blank.
        idx = field_map.get(field)
        if idx is None or idx >= len(cells):
            return None
        return cells[idx]
    
    record = ContactRecord.build(
        first_name=get(ContactField.FIRST_NAME),
        last_name=get(ContactField.LAST_NAME),
        full_name=get(ContactField.FULL_NAME),
        email=get(ContactField.EMAIL),
        company=get(ContactField.COMPANY),
        job_title=get(ContactField.JOB_TITLE),
        country=get(ContactField.COUNTRY),
    )
    return record if record.has_identifier() else None