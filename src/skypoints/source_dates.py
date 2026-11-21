import re
from datetime import date


class AmbiguousDateError(ValueError):
    """The text is a valid date under more than one reading."""


def _as_date(year: int, month: int, day: int):
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _candidate_readings(text: str) -> list:
    slashed = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if slashed:
        first, second, year = (int(part) for part in slashed.groups())
        return [(year, first, second), (year, second, first)]

    digits = re.fullmatch(r"(\d{3,4})(\d{4})", text)
    if digits:
        prefix, year = digits.group(1), int(digits.group(2))
        readings = []
        for split in (1, 2):
            first, second = prefix[:split], prefix[split:]
            if 1 <= len(second) <= 2:
                readings += [(year, int(first), int(second)), (year, int(second), int(first))]
        return readings

    iso = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if iso:
        year, month, day = (int(part) for part in iso.groups())
        return [(year, month, day)]

    raise ValueError(f"Unrecognised date format: {text!r}")


def parse_unambiguous_date(text: str) -> date:
    """Accept a date only if every possible reading of the text gives the same calendar day."""
    readings = {_as_date(*reading) for reading in _candidate_readings(text.strip())} - {None}
    if not readings:
        raise ValueError(f"Not a valid date under any reading: {text!r}")
    if len(readings) > 1:
        raise AmbiguousDateError(f"Ambiguous date {text!r}: could be {sorted(readings)}")
    return readings.pop()
    