"""String normalisation helpers shared across dedup strategies.

Latin-only inputs are assumed: stripping accents uses unicodedata's NFD +
combining-mark filter.
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from ..model import ContactRecord

_WHITESPACE = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s]")
_LEGAL_SUFFIX = re.compile(
    r"\b(inc|ltd|corp|corporation|llc|gmbh|plc|s\.a\.|co)\b\.?",
    re.IGNORECASE,
)
# Generic words that rarely carry identity. Kept conservative: 'solutions',
# 'services', 'technologies', 'systems', 'consulting' are intentionally excluded
# because they distinguish many small firms ("Acme Solutions" vs "Acme Services").
_NOISE_TOKENS = re.compile(
    r"\b(group|holdings?|international|intl|global|worldwide|enterprises)\b",
    re.IGNORECASE,
)
# Country / nationality tokens we see attached to local subsidiaries
# ("Acme Vietnam", "Acme India"). Extend as offenders appear in the data.
# Used as a fallback when the record has no country field; the per-record
# country strip in normalise_company is the more precise mechanism.
_COUNTRY_TOKENS = re.compile(
    r"\b("
    r"vietnam|vietnamese|"
    r"usa|united states|"
    r"uk|united kingdom|"
    r"india|indian|"
    r"china|chinese|"
    r"japan|japanese|"
    r"korea|korean|"
    r"singapore|singaporean|"
    r"thailand|thai|"
    r"indonesia|indonesian|"
    r"malaysia|malaysian|"
    r"philippines|filipino|"
    r"germany|german|"
    r"france|french|"
    r"brazil|brazilian|"
    r"mexico|mexican|"
    r"canada|canadian|"
    r"australia|australian"
    r")\b",
    re.IGNORECASE,
)


def strip_accents(value: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", value) if unicodedata.category(c) != "Mn"
    )


@lru_cache(maxsize=None)
def normalise_string(value: str) -> str:
    """Accent strip → lowercase → punctuation strip → collapse whitespace.

    Cached: the same field values recur across strategies and every transitive
    pass, and the function is pure, so memoising collapses the repeated regex work.
    """
    cleaned = _PUNCT.sub(" ", strip_accents(value).lower())
    return _WHITESPACE.sub(" ", cleaned).strip()


@lru_cache(maxsize=None)
def normalise_company(value: str, country: str | None = None) -> str:
    """normalise_string + strip legal suffixes + strip generic noise words +
    strip country/nationality tokens.

    When `country` is provided (the record's own country field), its normalised
    tokens are stripped from the name as well. This catches local-subsidiary
    naming like "Acme Vietnam" when the record's country is Vietnam, without
    risking over-stripping country names that are part of the brand
    ("Bank of America")."""
    cleaned = normalise_string(value)
    cleaned = _LEGAL_SUFFIX.sub("", cleaned)
    cleaned = _NOISE_TOKENS.sub("", cleaned)
    cleaned = _COUNTRY_TOKENS.sub("", cleaned)
    if country is not None:
        for token in normalise_string(country).split():
            if len(token) > 1:
                cleaned = re.sub(rf"\b{re.escape(token)}\b", "", cleaned)
    return _WHITESPACE.sub(" ", cleaned).strip()

def key_for(record: ContactRecord) -> str | None:
    """`<normalised resolved name>|<normalised company>` or None if either is missing."""
    name = record.resolved_full_name()
    if name is None or record.company is None:
        return None
    return f"{normalise_string(name)}|{normalise_company(record.company, record.country)}"


def tokenise_name(value: str) -> list[str]:
    """Split + drop single-char tokens after normalisation."""
    return [t for t in normalise_string(value).split() if len(t) > 1]