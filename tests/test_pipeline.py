from datetime import date

from skypoints.pipeline import run_pipeline

HEADER = "|H|Member_Name|Member_Id|Enrollment_Date|Last_Flight_Date|Tier_Code|Agent_Name|State|Country|DOB|Is_Active"
AS_OF = date(2024, 1, 15)


def test_valid_member_is_routed_to_its_country_with_derived_fields():
    files = [("MEMBERS_20240101.txt", [
        HEADER,
        "|D|Mateo|223459|20101012|20121013|GLD|Sam|NCR|PHIL|03051985|A",
    ])]

    result = run_pipeline(files, as_of=AS_OF)

    [mateo] = result["by_country"]["PHL"]
    assert mateo["member_id"] == "223459"
    assert mateo["age"] == 38
    assert mateo["stale_member"] is True
    assert result["quarantine"] == []


def test_invalid_records_are_quarantined_with_reasons():
    files = [("MEMBERS_20240102.txt", [
        HEADER,
        "|D|Mike|223460|1052022|20230101|PLT|Sam|CA|USA|NULL|A",
        "|D|Lena|223462|20230101|20231016|SLV|Sam|XX|XYZ|03051985|A",
        "|D|Omar|223463|20230101|20231017|GLD|Sam|VIC|AU|90210|03051985|A",
    ])]

    result = run_pipeline(files, as_of=AS_OF)

    assert result["by_country"] == {}
    assert [(q["line"], q["reasons"]) for q in result["quarantine"]] == [
        (2, ["INVALID_ENROLLMENT_DATE"]),
        (3, ["UNKNOWN_COUNTRY"]),
        (4, ["MALFORMED_RECORD"]),
    ]


def test_member_who_moved_appears_only_in_latest_country():
    files = [
        ("MEMBERS_20240101.txt", [HEADER, "|D|Ravi|223458|20101012|20121013|SLV|Sam|TN|IND|03051985|A"]),
        ("MEMBERS_20240102.txt", [HEADER, "|D|Ravi|223458|20101012|20231016|SLV|Sam|NY|USA|03051985|A"]),
    ]

    result = run_pipeline(files, as_of=AS_OF)

    assert list(result["by_country"]) == ["USA"]