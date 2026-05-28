from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UserSettings:
    """User-controlled options threaded into the dedup pipeline.

    Add new fields here rather than growing the run() signature.
    """

    drop_rows_without_email: bool = True
