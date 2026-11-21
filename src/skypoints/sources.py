import csv
import sys
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook

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
MANDATORY_FIELDS = ("source_id", "member_name", "enrollment_date")


def _is_missing(value) -> bool:
    return value is None or is_blank(str(value))


def read_source_date(value):
    """A date from a source cell: Excel dates pass through, blanks become None, text must be unambiguous."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if _is_missing(value):
        return None
    return parse_unambiguous_date(str(value))


def standardise_row(country: str, row: dict) -> tuple:
    """Rename one source row's columns to standard fields; return it with the reasons it can't be trusted."""
    columns = SOURCE_COLUMNS[country]
    missing_columns = sorted(set(columns) - set(row))
    unexpected_columns = sorted(set(row) - set(columns))
    if missing_columns or unexpected_columns:
        raise ValueError(
            f"{country} row does not match the expected layout: "
            f"missing {missing_columns}, unexpected {unexpected_columns}"
        )

    record = {columns[name]: value for name, value in row.items()}
    record["country"] = country
    record["member_key"] = f"{country}-{record['source_id']}"

    reasons = [f"MISSING_{field.upper()}" for field in MANDATORY_FIELDS if _is_missing(record[field])]
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


def read_source_rows(path: Path) -> list:
    """Rows of a CSV or Excel file as {column: value} dicts, skipping empty rows."""
    if path.suffix.lower() == ".xlsx":
        rows = load_workbook(path, read_only=True).active.iter_rows(values_only=True)
        header = next(rows)
        return [dict(zip(header, row)) for row in rows if any(value is not None for value in row)]
    with path.open(newline="") as handle:
        return [row for row in csv.DictReader(handle) if any(row.values())]


def load_provided_sources(folder: Path) -> dict:
    """Standardise every country file in folder; the country comes from the file name (e.g. AUS.xlsx)."""
    members = []
    quarantine = []
    for path in sorted(folder.iterdir()):
        country = path.stem.upper()
        if country not in SOURCE_COLUMNS:
            continue
        for row in read_source_rows(path):
            record, reasons = standardise_row(country, row)
            if reasons:
                quarantine.append({"member_key": record["member_key"], "file": path.name, "reasons": reasons})
            else:
                members.append(record)
    return {"members": members, "quarantine": quarantine}


def main() -> None:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "data" / "provided"
    result = load_provided_sources(folder)

    print(f"Readable members ({len(result['members'])}):")
    for record in result["members"]:
        print(f"  {record['member_key']}: {record['member_name']}")

    print(f"\nQuarantined ({len(result['quarantine'])}):")
    for item in result["quarantine"]:
        print(f"  {item['member_key']} ({item['file']}): {', '.join(item['reasons'])}")


if __name__ == "__main__":
    main()