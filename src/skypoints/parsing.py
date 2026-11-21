DETAIL_FIELDS = (
    "member_name",
    "member_id",
    "enrollment_date",
    "last_flight_date",
    "tier_code",
    "agent_name",
    "state",
    "country",
    "dob",
    "is_active",
)


def parse_detail_record(line: str) -> dict:
    """Split a pipe-delimited detail (D) record into named fields."""
    parts = line.split('|')
    if len(parts) < 2 or parts[1] != "D":
        raise ValueError(f"Expected a detail (D) record: {line!r}")

    values = parts[2:]
    if len(values) != len(DETAIL_FIELDS):
        raise ValueError(
            f"Expected {len(DETAIL_FIELDS)} fields, got {len(values)}: {line}"
        )
    return dict(zip(DETAIL_FIELDS, values))