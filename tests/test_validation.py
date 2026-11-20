import pytest

from skypoints.validation import find_missing_mandatory_fields


def valid_record():
    return {
        "member_name": "Elena",
        "member_id": "223457",
        "enrollment_date": "20101012",
        "last_flight_date": "20121013",
        "tier_code": "GLD",
        "agent_name": "Sam",
        "state": "CA",
        "country": "USA",
        "dob": "03051985",
        "is_active": "A",
    }


def test_complete_record_has_no_missing_mandatory_fields():
    assert find_missing_mandatory_fields(valid_record()) == []


@pytest.mark.parametrize("blank_value", ["", "   ", "NULL"])
def test_blank_or_null_text_counts_as_missing(blank_value):
    record = valid_record()
    record["member_id"] = blank_value

    assert find_missing_mandatory_fields(record) == ["member_id"]


def test_reports_every_missing_mandatory_field():
    record = valid_record()
    record["member_name"] = ""
    record["enrollment_date"] = ""

    assert find_missing_mandatory_fields(record) == ["member_name", "enrollment_date"]