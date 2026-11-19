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