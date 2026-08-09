"""Validation and coercion for uploaded data.

Reports gaps rather than throwing: a hackathon demo that dies on one malformed
row is worse than one that ingests 2,847 of 2,850 and says so.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class ValidationReport:
    source: str
    rows_seen: int = 0
    rows_loaded: int = 0
    missing_columns: list[str] = field(default_factory=list)
    unmapped_columns: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def rows_rejected(self) -> int:
        return self.rows_seen - self.rows_loaded

    @property
    def ok(self) -> bool:
        return not self.missing_columns and self.rows_loaded > 0

    def as_dict(self) -> dict:
        return {
            "source": self.source,
            "rows_seen": self.rows_seen,
            "rows_loaded": self.rows_loaded,
            "rows_rejected": self.rows_rejected,
            "missing_columns": self.missing_columns,
            "unmapped_columns": self.unmapped_columns,
            "errors": self.errors[:20],
            "ok": self.ok,
        }


def to_float(value, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def to_int(value, default: int = 0) -> int:
    return int(to_float(value, default))


def to_bool(value, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "t"}


_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d")


def to_date(value) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()[:10]
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def to_datetime(value) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    d = to_date(text)
    return datetime.combine(d, datetime.min.time()) if d else None


def require(report: ValidationReport, row: dict, columns: tuple[str, ...]) -> bool:
    for column in columns:
        if row.get(column) in (None, ""):
            report.errors.append(f"row {report.rows_seen}: missing '{column}'")
            return False
    return True
