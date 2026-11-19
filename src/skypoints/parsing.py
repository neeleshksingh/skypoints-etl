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
    return dict(zip(DETAIL_FIELDS, parts[2:]))