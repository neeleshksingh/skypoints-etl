def parse_detail_record(line: str) -> dict:
    """Split a pipe-delimited detail (D) record into named fields."""
    parts = line.split('|')

    record = {
        "member_name": parts[2],
        "member_id": parts[3],
        "dob": parts[10]
    }

    return record