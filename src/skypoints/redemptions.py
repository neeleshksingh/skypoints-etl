def flatten_redemptions(feed: dict) -> list:
    """One row per redemption, carrying the parent member_id and feed_date; repeated txn_ids kept once."""
    rows = []
    seen_txn_ids = set()
    for redemption in feed["redemptions"]:
        if redemption["txn_id"] in seen_txn_ids:
            continue
        seen_txn_ids.add(redemption["txn_id"])
        rows.append({
            "member_id": feed["member_id"],
            "feed_date": feed["feed_date"],
            **redemption,
        })
    return rows