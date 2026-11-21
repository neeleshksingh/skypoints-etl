from datetime import date

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