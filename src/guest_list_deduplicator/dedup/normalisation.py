"""String normalisation helpers shared across dedup strategies.

Assumes Latin-script input. Accent stripping works via unicodedata NFD
decomposition followed by removal of combining marks.
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
# Generic words that rarely carry identity. More specific words like 'solutions'
# and 'services' are left in because they distinguish many small firms
# ("Acme Solutions" vs "Acme Services").
_NOISE_TOKENS = re.compile(
    r"\b(group|holdings?|international|intl|global|worldwide|enterprises)\b",
    re.IGNORECASE,
)
# Country/nationality tokens commonly attached to local subsidiaries
# ("Acme Vietnam", "Acme India"). Extend as offenders appear in the data.
# Used as a fallback when the record has no country field; see the 'country'
# parameter in normalise_company for the more precise per-record strip.
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
    """Decompose to NFD and drop combining marks, effectively stripping accents."""
    return "".join(
        c for c in unicodedata.normalize("NFD", value) if unicodedata.category(c) != "Mn"
    )


@lru_cache(maxsize=None)
def normalise_string(value: str) -> str:
    """Strip accents, lowercase, remove punctuation, collapse whitespace.

    Results are cached because the same field values recur across strategies
    and transitive passes, and the function is pure.
    """
    cleaned = _PUNCT.sub(" ", strip_accents(value).lower())
    return _WHITESPACE.sub(" ", cleaned).strip()


@lru_cache(maxsize=None)
def normalise_company(value: str, country: str | None = None) -> str:
    """Apply normalise_string, then strip legal suffixes, generic noise words,
    and country/nationality tokens.

    When 'country' is provided (taken from the record's own country field),
    its normalised tokens are also stripped from the name. This handles
    local-subsidiary names like "Acme Portugal" when the record's country is
    Portugal, without over-stripping country names that are part of a brand
    (e.g. "Bank of America")."""
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
    """Return '<normalised resolved name>|<normalised company>', or None if either part is missing."""
    name = record.resolved_full_name()
    if name is None or record.company is None:
        return None
    return f"{normalise_string(name)}|{normalise_company(record.company, record.country)}"


def tokenise_name(value: str) -> list[str]:
    """Normalise the name then split it into tokens, dropping any single-character ones."""
    return [t for t in normalise_string(value).split() if len(t) > 1]