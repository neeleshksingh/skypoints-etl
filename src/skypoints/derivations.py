from datetime import date
from typing import Optional

STALE_AFTER_DAYS = 90


def calculate_age(dob: date, as_of: date) -> int:
    """Whole years from dob to as_of; this year's birthday counts only once reached."""
    age = as_of.year - dob.year
    if (as_of.month, as_of.day) < (dob.month, dob.day):
        age -= 1
    return age


def is_stale_member(last_flight_date: Optional[date], as_of: date) -> Optional[bool]:
    """Stale when the last flight is more than STALE_AFTER_DAYS before as_of; None if unknown."""
    if last_flight_date is None:
        return None
    return (as_of - last_flight_date).days > STALE_AFTER_DAYS