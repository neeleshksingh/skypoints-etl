import pytest

from skypoints.parsing import parse_detail_record


def test_parses_detail_record_into_named_fields():
    # Arrange
    line = "|D|Elena|223457|20101012|20121013|GLD|Sam|CA|USA|03051985|A"

    # Act
    record = parse_detail_record(line)

    # Assert
    assert record == {
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


def test_rejects_detail_record_with_wrong_field_count():
    line = "|D|Elena|223457|20101012|20121013|GLD|Sam|CA|USA|90210|03051985|A"

    with pytest.raises(ValueError):
        parse_detail_record(line)


def test_rejects_line_that_is_not_a_detail_record():
    line = "|H|Member_Name|Member_Id|Enrollment_Date|Last_Flight_Date|Tier_Code|Agent_Name|State|Country|DOB|Is_Active"

    with pytest.raises(ValueError):
        parse_detail_record(line)


@pytest.mark.parametrize("line", ["", "no delimiters here"])
def test_rejects_line_without_record_structure(line):
    with pytest.raises(ValueError):
        parse_detail_record(line)