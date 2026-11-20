from datetime import date


def calculate_age(dob: date, as_of: date) -> int:
    """Whole years from dob to as_of; this year's birthday counts only once reached."""
    age = as_of.year - dob.year
    if (as_of.month, as_of.day) < (dob.month, dob.day):
        age -= 1
    return age