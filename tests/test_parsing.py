from skypoints.parsing import parse_detail_record


def test_parses_detail_record_into_named_fields():
    # Arrange
    line = "|D|Elena|223457|20101012|20121013|GLD|Sam|CA|USA|03051985|A"

    # Act
    record = parse_detail_record(line)

    # Assert
    assert record["member_name"] == "Elena"
    assert record["member_id"] == "223457"
    assert record["dob"] == "03051985"