from datetime import date

from skypoints.deduplication import latest_record_per_member
from skypoints.routing import group_by_country


def member(member_id, country, file_date=date(2024, 1, 1), line_number=1):
    return {
        "member_id": member_id,
        "country": country,
        "file_date": file_date,
        "line_number": line_number,
    }


def test_groups_members_by_country():
    elena = member("223457", "USA")
    ravi = member("223458", "IND")
    nora = member("22345", "CAN")

    groups = group_by_country([elena, ravi, nora])

    assert groups == {"USA": [elena], "IND": [ravi], "CAN": [nora]}


def test_member_who_moved_lands_only_in_new_country():
    old = member("223458", "IND", date(2024, 1, 1))
    new = member("223458", "USA", date(2024, 1, 2))

    latest = latest_record_per_member([old, new])
    groups = group_by_country(latest.values())

    assert groups == {"USA": [new]}