from datetime import date, datetime


def parse_date(value: str, fmt: str) -> date:
    """Parse a date string using an explicit format, never a guessed one."""
    return datetime.strptime(value, fmt).date()