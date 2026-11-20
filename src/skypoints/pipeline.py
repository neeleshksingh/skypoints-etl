import re
import sys
from datetime import date
from pathlib import Path

from skypoints.countries import normalize_country
from skypoints.dates import parse_date
from skypoints.deduplication import latest_record_per_member
from skypoints.derivations import calculate_age, is_stale_member
from skypoints.parsing import parse_detail_record
from skypoints.routing import group_by_country
from skypoints.validation import find_missing_mandatory_fields, is_blank

DATE_FORMATS = {
    "enrollment_date": "%Y%m%d",
    "last_flight_date": "%Y%m%d",
    "dob": "%m%d%Y",
}


def file_business_date(file_name: str) -> date:
    """Business date from a name like MEMBERS_20240102.txt."""
    match = re.search(r"\d{8}", file_name)
    if match is None:
        raise ValueError(f"No YYYYMMDD business date in file name: {file_name!r}")
    return parse_date(match.group(), "%Y%m%d")


def process_line(line: str, file_date: date, line_number: int, as_of: date) -> tuple:
    """Return (clean record, []) or (None, reasons it was rejected)."""
    try:
        record = parse_detail_record(line)
    except ValueError:
        return None, ["MALFORMED_RECORD"]

    reasons = [f"MISSING_{field.upper()}" for field in find_missing_mandatory_fields(record)]

    for column, fmt in DATE_FORMATS.items():
        if is_blank(record[column]):
            record[column] = None
            continue
        try:
            record[column] = parse_date(record[column], fmt)
        except ValueError:
            reasons.append(f"INVALID_{column.upper()}")

    try:
        record["country"] = normalize_country(record["country"])
    except ValueError:
        reasons.append("UNKNOWN_COUNTRY")

    if reasons:
        return None, reasons

    record["age"] = calculate_age(record["dob"], as_of) if record["dob"] else None
    record["stale_member"] = is_stale_member(record["last_flight_date"], as_of)
    record["file_date"] = file_date
    record["line_number"] = line_number
    return record, []


def run_pipeline(files: list, as_of: date) -> dict:
    """files: [(file_name, lines)]. Returns current members grouped by country, plus the quarantine."""
    valid = []
    quarantine = []
    for file_name, lines in files:
        file_date = file_business_date(file_name)
        for line_number, line in enumerate(lines, start=1):
            if line.startswith("|H|"):
                continue
            record, reasons = process_line(line, file_date, line_number, as_of)
            if reasons:
                quarantine.append({"file": file_name, "line": line_number, "reasons": reasons, "raw": line})
            else:
                valid.append(record)

    latest = latest_record_per_member(valid)
    return {"by_country": group_by_country(latest.values()), "quarantine": quarantine}


def main() -> None:
    samples = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "data" / "samples"
    files = [(path.name, path.read_text().splitlines()) for path in sorted(samples.glob("MEMBERS_*.txt"))]
    as_of = date(2024, 1, 15)

    result = run_pipeline(files, as_of=as_of)

    print(f"Members by country (as of {as_of}):")
    for country, members in sorted(result["by_country"].items()):
        names = ", ".join(f"{m['member_name']} ({m['member_id']})" for m in members)
        print(f"  {country}: {names}")

    print(f"\nQuarantined ({len(result['quarantine'])}):")
    for item in result["quarantine"]:
        print(f"  {item['file']} line {item['line']}: {', '.join(item['reasons'])}")


if __name__ == "__main__":
    main()