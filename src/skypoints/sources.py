from skypoints.source_dates import parse_unambiguous_date

SOURCE_COLUMNS = {
    "AUS": {
        "Unique ID": "source_id",
        "Member Name": "member_name",
        "Tier Type": "tier_code",
        "Date of Birth": "dob",
        "Date of Enrollment": "enrollment_date",
        "Date of Flight": "last_flight_date",
    },
    "USA": {
        "ID": "source_id",
        "Name": "member_name",
        "TierCode": "tier_code",
        "EnrollmentDate": "enrollment_date",
        "FlightDate": "last_flight_date",
    },
    "IND": {
        "ID": "source_id",
        "Name": "member_name",
        "DOB": "dob",
        "TierCode": "tier_code",
        "EnrollmentDate": "enrollment_date",
        "Individual or Corporate": "member_type",
        "Flight Date": "last_flight_date",
    },
}

DATE_FIELDS = ("dob", "enrollment_date", "last_flight_date")


def standardise_row(country: str, row: dict) -> tuple:
    """Rename one source row's columns to standard fields and give it a country-scoped key."""
    columns = SOURCE_COLUMNS[country]
    record = {columns[name]: value for name, value in row.items()}
    record["country"] = country
    record["member_key"] = f"{country}-{record['source_id']}"
    for field in DATE_FIELDS:
        if field in record:
            record[field] = parse_unambiguous_date(str(record[field]))
    return record, []