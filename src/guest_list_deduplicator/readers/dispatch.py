"""Suffix-based dispatch for reading spreadsheets.

Replaces Java's FileReaderFactory + IFileReader interface. Callers go through
list_sheets() and read() rather than instantiating a reader class.
"""
from __future__ import annotations

from pathlib import Path

from ..model import SheetData


def list_sheets(path: Path) -> list[str]:
    """Return visible sheet names. CSV → single synthetic sheet named after the file."""
    raise NotImplementedError


def read(path: Path, sheet_selection: list[str]) -> dict[str, SheetData]:
    """Read selected sheets into a {sheet_name: SheetData} map preserving order.

    Headers are resolved via header_resolver. Rows failing
    ContactRecord.has_identifier() are dropped during mapping.
    """
    raise NotImplementedError
