from datetime import date, datetime

import pytest

from skypoints.sources import standardise_row

USA_ROW = {"ID": "1", "Name": "Sam", "TierCode": "PLT", "EnrollmentDate": "6152022", "FlightDate": "8202022"}


def test_maps_source_columns_to_standard_fields():
    record, reasons = standardise_row("USA", USA_ROW)

    assert record["member_name"] == "Sam"
    assert record["tier_code"] == "PLT"
    assert record["country"] == "USA"
    assert record["enrollment_date"] == date(2022, 6, 15)
    assert record["last_flight_date"] == date(2022, 8, 20)
    assert reasons == []


def test_same_source_id_in_two_countries_gives_two_different_members():
    aus_row = {"Unique ID": "1", "Member Name": "Mike", "Tier Type": "PLT",
               "Date of Birth": "1997-12-13", "Date of Enrollment": "2022-05-11", "Date of Flight": "2022-08-01"}

    usa, _ = standardise_row("USA", USA_ROW)
    aus, _ = standardise_row("AUS", aus_row)

    assert usa["member_key"] == "USA-1"
    assert aus["member_key"] == "AUS-1"

def test_ambiguous_dates_become_reasons_instead_of_guesses():
    john = {"ID": "2", "Name": "John", "TierCode": "SLV", "EnrollmentDate": "1052022", "FlightDate": "1152022"}

    record, reasons = standardise_row("USA", john)

    assert reasons == ["AMBIGUOUS_ENROLLMENT_DATE", "AMBIGUOUS_LAST_FLIGHT_DATE"]
    assert record["enrollment_date"] is None


def test_impossible_date_becomes_invalid_reason():
    jonnathan = {"Unique ID": 2, "Member Name": "Jonnathan", "Tier Type": "GLD",
                 "Date of Birth": datetime(1997, 12, 13), "Date of Enrollment": "2021-13-13",
                 "Date of Flight": datetime(2022, 1, 5)}

    _, reasons = standardise_row("AUS", jonnathan)

    assert reasons == ["INVALID_ENROLLMENT_DATE"]


@pytest.mark.parametrize("blank", ["NULL", "", None])
def test_blank_optional_date_is_missing_not_an_error(blank):
    mike = {"Unique ID": 1, "Member Name": "Mike", "Tier Type": "PLT", "Date of Birth": blank,
            "Date of Enrollment": datetime(2022, 5, 11), "Date of Flight": datetime(2022, 8, 1)}

    record, reasons = standardise_row("AUS", mike)

    assert record["dob"] is None
    assert record["enrollment_date"] == date(2022, 5, 11)
    assert reasons == []

@pytest.mark.parametrize(
    "column, reason",
    [
        ("ID", "MISSING_SOURCE_ID"),
        ("Name", "MISSING_MEMBER_NAME"),
        ("EnrollmentDate", "MISSING_ENROLLMENT_DATE"),
    ],
)
def test_blank_mandatory_field_is_reported_as_missing(column, reason):
    row = {**USA_ROW, column: ""}

    _, reasons = standardise_row("USA", row)

    assert reasons == [reason]


def test_row_with_unexpected_layout_is_rejected_with_a_clear_error():
    row = {column: value for column, value in USA_ROW.items() if column != "ID"}

    with pytest.raises(ValueError, match=r"missing \['ID'\]"):
        standardise_row("USA", row)