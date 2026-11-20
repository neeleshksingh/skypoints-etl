from typing import Iterable


def group_by_country(records: Iterable[dict]) -> dict:
    """Group member records by their (already normalized) country code."""
    groups = {}
    for record in records:
        groups.setdefault(record["country"], []).append(record)
    return groups