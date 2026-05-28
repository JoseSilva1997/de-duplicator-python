"""String normalisation helpers shared across dedup strategies.

Latin-only inputs are assumed: stripping accents uses unicodedata's NFD +
combining-mark filter.
"""
from __future__ import annotations

import re
import unicodedata

from ..model import ContactRecord

_WHITESPACE = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s]")
_LEGAL_SUFFIX = re.compile(
    r"\b(inc|ltd|corp|corporation|llc|gmbh|plc|s\.a\.|co)\b\.?",
    re.IGNORECASE,
)


def strip_accents(value: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", value) if unicodedata.category(c) != "Mn"
    )


def normalise_string(value: str) -> str:
    """Accent strip → lowercase → trim → collapse whitespace."""
    return _WHITESPACE.sub(" ", strip_accents(value).lower().strip())


def normalise_company(value: str) -> str:
    """normalise_string + strip legal suffixes + drop punctuation."""
    cleaned = _LEGAL_SUFFIX.sub("", normalise_string(value))
    cleaned = _PUNCT.sub("", cleaned)
    return _WHITESPACE.sub(" ", cleaned).strip()


def key_for(record: ContactRecord) -> str | None:
    """`<normalised resolved name>|<normalised company>` or None if either is missing."""
    name = record.resolved_full_name()
    if name is None or record.company is None:
        return None
    return f"{normalise_string(name)}|{normalise_company(record.company)}"


def tokenise_name(value: str) -> list[str]:
    """Split + drop single-char tokens after normalisation."""
    return [t for t in normalise_string(value).split() if len(t) > 1]