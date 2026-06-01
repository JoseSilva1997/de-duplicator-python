from __future__ import annotations

import re
from dataclasses import dataclass

_WHITESPACE = re.compile(r"\s+")


def _normalise(value: str | None) -> str | None:
    """Collapse internal whitespace, strip leading/trailing space.
    Return None for blank or missing values."""
    if value is None:
        return None
    cleaned = _WHITESPACE.sub(" ", value.strip())
    return cleaned or None


@dataclass(frozen=True, slots=True)
class ContactRecord:
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    email: str | None = None
    company: str | None = None
    job_title: str | None = None
    country: str | None = None

    @classmethod
    def build(
        cls,
        *,
        first_name: str | None = None,
        last_name: str | None = None,
        full_name: str | None = None,
        email: str | None = None,
        company: str | None = None,
        job_title: str | None = None,
        country: str | None = None,
    ) -> "ContactRecord":
        """Construct a record with all string fields normalised (whitespace
        collapsed, empties → None) and email lowercased."""
        e = _normalise(email)
        return cls(
            first_name=_normalise(first_name),
            last_name=_normalise(last_name),
            full_name=_normalise(full_name),
            email=e.lower() if e is not None else None,
            company=_normalise(company),
            job_title=_normalise(job_title),
            country=_normalise(country),
        )

    def is_empty(self) -> bool:
        """True only when every field on this ContactRecord is None."""
        return all(
            v is None
            for v in (
                self.first_name,
                self.last_name,
                self.full_name,
                self.email,
                self.company,
                self.job_title,
                self.country,
            )
        )

    def has_identifier(self) -> bool:
        """At least one identifying field (email or any name) is present."""
        return (
            self.email is not None
            or self.first_name is not None
            or self.last_name is not None
            or self.full_name is not None
        )

    def has_name(self) -> bool:
        """Either a full-name field or both first and last."""
        return self.full_name is not None or (
            self.first_name is not None and self.last_name is not None
        )

    def resolved_full_name(self) -> str | None:
        """Return full_name if present, otherwise join first_name and last_name. Returns None if neither combination is available."""
        if self.full_name is not None:
            return self.full_name
        if self.first_name is not None and self.last_name is not None:
            return f"{self.first_name} {self.last_name}"
        return None
