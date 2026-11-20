from skypoints.redemptions import flatten_redemptions


def txn(txn_id, miles=1000):
    return {
        "txn_id": txn_id,
        "txn_date": "20240110",
        "partner": "AeroLink",
        "miles_redeemed": miles,
        "status": "COMPLETED",
    }


def test_flattens_each_redemption_into_a_row_with_parent_fields():
    feed = {
        "member_id": "223457",
        "feed_date": "20240115",
        "redemptions": [
            {"txn_id": "RX10091", "txn_date": "20240110", "partner": "AeroLink",
             "miles_redeemed": 12000, "status": "COMPLETED"},
            {"txn_id": "RX10092", "txn_date": "20240113", "partner": "SkyPoints",
             "miles_redeemed": 5000, "status": "PENDING"},
        ],
    }

    rows = flatten_redemptions(feed)

    assert rows == [
        {"member_id": "223457", "feed_date": "20240115", "txn_id": "RX10091",
         "txn_date": "20240110", "partner": "AeroLink",
         "miles_redeemed": 12000, "status": "COMPLETED"},
        {"member_id": "223457", "feed_date": "20240115", "txn_id": "RX10092",
         "txn_date": "20240113", "partner": "SkyPoints",
         "miles_redeemed": 5000, "status": "PENDING"},
    ]


def test_member_with_no_redemptions_produces_no_rows():
    feed = {"member_id": "223457", "feed_date": "20240115", "redemptions": []}

    assert flatten_redemptions(feed) == []


def test_duplicate_transaction_is_kept_only_once():
    feed = {
        "member_id": "223457",
        "feed_date": "20240115",
        "redemptions": [txn("RX10091"), txn("RX10091")],
    }

    rows = flatten_redemptions(feed)

    assert [row["txn_id"] for row in rows] == ["RX10091"]