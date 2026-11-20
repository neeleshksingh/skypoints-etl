from datetime import date, datetime


def parse_date(value: str, fmt: str) -> date:
    """Parse an 8-digit date with an explicit format; reject anything ambiguous."""
    if len(value) != 8:
        raise ValueError(f"Expected an 8-digit date, got: {value!r}")
    return datetime.strptime(value, fmt).date()