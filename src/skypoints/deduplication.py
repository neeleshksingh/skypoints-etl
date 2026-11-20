def recency(record: dict) -> tuple:
    """Sort key for 'latest record wins': file business date first, then line order."""
    return (record["file_date"], record["line_number"])


def latest_record_per_member(records: list) -> dict:
    """Keep only the most recent record for each member_id."""
    latest = {}
    for record in records:
        member_id = record["member_id"]
        current = latest.get(member_id)
        if current is None or recency(record) > recency(current):
            latest[member_id] = record
    return latest