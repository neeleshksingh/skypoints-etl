from datetime import date, datetime

from skypoints.source_dates import AmbiguousDateError, parse_unambiguous_date
from skypoints.validation import is_blank

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


def read_source_date(value):
    """A date from a source cell: Excel dates pass through, blanks become None, text must be unambiguous."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None or is_blank(str(value)):
        return None
    return parse_unambiguous_date(str(value))


def standardise_row(country: str, row: dict) -> tuple:
    """Rename one source row's columns to standard fields; return it with the reasons it can't be trusted."""
    columns = SOURCE_COLUMNS[country]
    record = {columns[name]: value for name, value in row.items()}
    record["country"] = country
    record["member_key"] = f"{country}-{record['source_id']}"

    reasons = []
    for field in DATE_FIELDS:
        if field not in record:
            continue
        try:
            record[field] = read_source_date(record[field])
        except AmbiguousDateError:
            record[field] = None
            reasons.append(f"AMBIGUOUS_{field.upper()}")
        except ValueError:
            record[field] = None
            reasons.append(f"INVALID_{field.upper()}")
    return record, reasons