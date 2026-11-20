from datetime import date

from skypoints.deduplication import latest_record_per_member


def record(member_id, country, file_date, line_number):
    return {
        "member_id": member_id,
        "country": country,
        "file_date": file_date,
        "line_number": line_number,
    }


def test_record_from_newer_file_wins_when_member_moves_country():
    newer = record("223458", "USA", date(2024, 1, 2), line_number=1)
    older = record("223458", "IND", date(2024, 1, 1), line_number=5)

    latest = latest_record_per_member([newer, older])

    assert latest == {"223458": newer}


def test_later_line_wins_within_the_same_file():
    earlier = record("223458", "IND", date(2024, 1, 1), line_number=2)
    later = record("223458", "USA", date(2024, 1, 1), line_number=7)

    latest = latest_record_per_member([earlier, later])

    assert latest == {"223458": later}


def test_keeps_one_record_for_each_different_member():
    elena = record("223457", "USA", date(2024, 1, 1), line_number=1)
    ravi = record("223458", "IND", date(2024, 1, 1), line_number=2)

    latest = latest_record_per_member([elena, ravi])

    assert latest == {"223457": elena, "223458": ravi}