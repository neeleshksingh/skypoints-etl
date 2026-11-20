# SkyPoints ETL — Member Profile & Redemption Pipeline

Incubyte Data Engineer technical assessment.

> **Status:** In progress. Built incrementally with Test-Driven Development;
> the commit history shows how the solution evolved, one Red → Green → Refactor
> cycle at a time.

## Problem

SkyPoints receives two daily feeds from its source system:

1. A pipe-delimited flat file of member profiles (header + detail records)
2. A JSON feed of partner-airline mileage redemptions

The pipeline must load these into raw → staging → country-specific target
tables, derive `Age` and `Stale_Member`, apply a "latest record wins" rule when
a member moves country, flatten the redemption feed, and validate data quality —
at a scale of billions of records per day.

## Setup

Requires Python 3.9+. No third-party runtime dependencies; `pytest` for tests.

    python3 -m venv .venv
    source .venv/bin/activate
    pip install pytest

## Running tests

    pytest

## Project structure

    src/skypoints/
        parsing.py        Split a pipe-delimited detail record into named fields
        dates.py          Strict date parsing with an explicit format per column
        derivations.py    Age and Stale_Member, computed as of a business date
        countries.py      Normalise source country codes to ISO alpha-3
        validation.py     Mandatory-field checks (incl. "NULL" text and blanks)
        deduplication.py  "Latest record wins" per member
        routing.py        Group current member records by country
        redemptions.py    Flatten the JSON redemption feed (in progress)
    tests/                pytest suite — the executable specification of every rule
    sql/                  Snowflake DDL and set-based transformation scripts (planned)
    data/samples/         Sample input files used in tests and demos

## Approach

- **Python is the tested specification.** Every business rule is a small, pure
  function developed test-first.
- **SQL is the scaled implementation.** At billions of rows per day, row-by-row
  Python is not viable. The `sql/` scripts implement the same rules set-based in
  Snowflake (`COPY INTO`, `QUALIFY ROW_NUMBER()`, `LATERAL FLATTEN`).
- **Single Source of Truth.** One conformed `member_current` table holds the
  latest record per member. Country tables are derived from it, generated from a
  country list rather than hand-written per country.

Pipeline order:

    parse → validate → normalise country → derive Age/Stale → latest record wins → route

Routing happens after deduplication, so a member who moved country is routed
exactly once, to their current country.

Known trade-off: rules exist in two places (Python and SQL). In production I
would test the SQL directly (e.g. dbt tests) and treat the Python as reference.

## Deliverables

| # | Deliverable | Status |
| --- | --- | --- |
| 1 | DDL for raw, staging and country target tables | Planned (Snowflake) |
| 2 | Staging with derived `Age` and `Stale_Member` | Rules implemented and tested in Python; SQL planned |
| 3 | Split into per-country tables, latest record wins | Rules implemented and tested in Python; SQL planned |
| 4 | Flatten JSON redemption feed and join to members | In progress |
| 5 | Data validations | Field count, record type, dates, mandatory fields, country codes done; more planned |
| 6 | Live demonstration | Planned |

## Assumptions

| Topic | Decision | Reason |
| --- | --- | --- |
| Business key | `Member_ID`, not `Member_Name` | The spec marks Name as key, but names are not unique ("Mike" appears in both the AUS and USA samples). Treated as a documentation error. |
| "Latest record wins" | Latest by file business date (from filename); line order within the file breaks ties | `Last_Flight_Date` describes the member, not how recent the record is. |
| Reference date for Age / Stale | A business date passed into the run, not `CURRENT_DATE` | Reruns are reproducible and tests are deterministic. |
| `Stale_Member` boundary | Stale only when days since flight is **> 90**; exactly 90 is not stale | Follows the spec literally. |
| Null `Last_Flight_Date` | `Stale_Member` is NULL (unknown) | Missing data is not evidence of staleness. |
| Leap-day birthdays | A 29 Feb birthday counts as reached on 1 Mar in non-leap years | Common convention; the age calculation never constructs an invalid date. |
| Date format | Exactly 8 digits with an explicit format per column | Python's `strptime` silently guesses 7-digit dates (`1052022` → 5 Oct); strict length prevents that. |
| Post Code | Stored as VARCHAR, not INT | INT loses leading zeros; some countries (e.g. Canada) use alphanumeric codes. |
| Missing values | Empty, whitespace-only and the literal text `NULL` all count as missing | The AUS sample stores `NULL` as text. |
| Unknown country codes | Rejected for quarantine, never guessed | A member in the wrong country table is worse than a held record. |
| Target table naming | `MEMBERS_<ISO alpha-3>` (e.g. `MEMBERS_IND`) rather than `Table_India` | Derived directly from the normalised code; no second name mapping to maintain. |
| Unparseable records | Quarantined with a reason, never guessed | A wrong value is worse than a rejected one. |

## Known data issues in the samples

| # | Source | Issue | Handling |
| --- | --- | --- | --- |
| 1 | Spec vs sample | Spec defines 11 fields (incl. Post Code); header and detail rows have 10 | **Implemented:** parser rejects a detail record whose field count differs from the layout |
| 2 | Spec | Member Name marked as key column | Use Member_ID (see Assumptions) |
| 3 | Intermediate table | DOB `03051985` became `3051985`: leading zero lost to an INT cast | **Implemented:** dates and IDs stay strings until explicitly parsed |
| 4 | Sample file | DOB is `MMDDYYYY`; other dates are `YYYYMMDD` | **Implemented:** each column parsed with its own explicit format |
| 5 | Intermediate table | Column named `County`; Agent_Name missing for 4 of 5 rows | Planned: raw-to-staging reconciliation check |
| 6 | Sample file | Country codes inconsistent: `PHIL` (4 chars), `AU` (2 chars) | **Implemented:** normalised to ISO alpha-3; unknown codes rejected |
| 7 | Sample file | Member IDs `22345` and `2256` shorter than others | Planned: warning (valid per spec, but possibly truncated) |
| 8 | AUS sample | Invalid date `2021-13-13`; literal string `NULL` | **Implemented:** impossible dates rejected; `NULL` text treated as missing |
| 9 | USA sample | Dates stored as numbers, e.g. `1052022`: ambiguous (1/05 or 10/5) | **Implemented:** rejected, cannot be parsed safely |
| 10 | IND sample | Extra `Individual` column not in spec | Planned: header/schema validation |
| 11 | IND sample | `3/5/2022`: day/month order ambiguous | **Implemented:** rejected by the strict 8-digit format |
| 12 | JSON feed | Partner `SkyPoints` is the programme itself; `PENDING` status | Flagged for business clarification; duplicate `txn_id` kept once (in progress) |
| 13 | Header line | Has the same field count as a detail record | **Implemented:** parser rejects any record type other than `D` |

## How I used AI

I used an AI assistant (Claude) as a pairing partner throughout. With a short
deadline, it drafted most of the test and implementation code; I ran every
Red → Green → Refactor cycle, reviewed each step before committing, and made
sure I can explain every line.

- **Analysis:** Asked it to review the spec and samples for data issues. I
  verified each finding against the source files before recording it above.
- **Caught by testing, not trust:** It flagged that Python's `strptime` silently
  parses the ambiguous `1052022` as 5 October. I confirmed this with a failing
  test before making date parsing strict.
- **Corrected my own test:** My first parser test used the DOB from the
  intermediate table (`3051985`), which would have locked in the leading-zero
  bug. I changed it to the raw source value.
- **Kept scope tight:** Rejected adding checks that no test required (e.g. a
  digits-only date check) to avoid untested code.

<!-- Keep adding entries: what you asked, what you accepted, what you rejected and why. -->

## Open questions for the business

- Should `PENDING` redemptions count towards a member's mileage balance?
- Is `SkyPoints` a valid partner value in the redemption feed?
- What is the date format convention for each country's source system? (The AUS
  sheet uses `YYYY-MM-DD`, which the compact 8-digit parser would reject.)
- Is a short Member ID such as `2256` valid, or truncated upstream?
