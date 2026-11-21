from pathlib import Path

from skypoints.sources import load_provided_sources

PROVIDED = Path(__file__).resolve().parents[1] / "data" / "provided"


def test_provided_files_split_into_clean_members_and_quarantine():
    result = load_provided_sources(PROVIDED)

    assert sorted(record["member_key"] for record in result["members"]) == [
        "AUS-1", "AUS-3", "IND-3", "USA-1", "USA-3",
    ]
    assert {item["member_key"]: item["reasons"] for item in result["quarantine"]} == {
        "AUS-2": ["INVALID_ENROLLMENT_DATE"],
        "IND-1": ["AMBIGUOUS_DOB"],
        "IND-2": ["AMBIGUOUS_ENROLLMENT_DATE", "AMBIGUOUS_LAST_FLIGHT_DATE"],
        "USA-2": ["AMBIGUOUS_ENROLLMENT_DATE", "AMBIGUOUS_LAST_FLIGHT_DATE"],
    }