# SkyPoints ETL — Member Profile & Redemption Pipeline

Incubyte Data Engineer technical assessment.

> **Status:** All five written deliverables are implemented. Business rules are
> developed test-first in Python; the same rules run set-based in Snowflake and
> have been verified against the sample data. The commit history shows how the
> solution evolved, one Red → Green → Refactor cycle at a time.

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

## Running the Python pipeline

    PYTHONPATH=src python3 -m skypoints.pipeline

Reads the member files in `data/samples/`, prints current members by country and
the quarantined records with their reasons. The result matches the Snowflake
output for the same files.

## Running the SQL (Snowflake)

Run in a Snowflake worksheet with a warehouse selected, in this order:

| Step | Action | Verified result on the sample data |
| --- | --- | --- |
| 1 | Run `01_raw_tables.sql` | Database, RAW / STAGING / CORE schemas, raw tables |
| 2 | Run `02_load_raw.sql` once | Creates the stage and file formats (no files to load yet) |
| 3 | Upload `data/samples/*` to stage `SKYPOINTS.RAW.SKYPOINTS_LANDING` | |
| 4 | Run `02_load_raw.sql` again | `MEMBER_PROFILE_RAW`: 12 rows (2 headers + 10 detail lines); `REDEMPTION_FEED_RAW`: 3 rows |
| 5 | Run `03_staging.sql` | `MEMBER_PROFILE_STG`: 10 rows, 6 VALID and 4 REJECTED |
| 6 | Run `04_core_country_split.sql` | `MEMBER_CURRENT`: 5 members (AUS 1, CAN 1, PHL 1, USA 2); `MEMBERS_IND`: 0 rows |
| 7 | Run `05_redemptions.sql` | `REDEMPTION_STG`: 3 transactions; `MEMBER_REDEMPTIONS`: 2 rows |
| 8 | Run `06_data_quality.sql` | `DQ_ISSUES`: REJECTED_RECORD 5, ORPHAN_REDEMPTION 1, PARTNER_IS_PROGRAMME 1, SHORT_MEMBER_ID 2 |

Running step 2 twice is intentional and safe: `IF NOT EXISTS` makes the DDL a
no-op the second time, and `COPY INTO` skips files it has already loaded.

`MEMBERS_IND` being empty is the proof of "latest record wins": Ravi was Indian
in the first file and moved to the USA in the second.

## Project structure

    src/skypoints/
        parsing.py        Split a pipe-delimited detail record into named fields
        dates.py          Strict date parsing with an explicit format per column
        derivations.py    Age and Stale_Member, computed as of a business date
        countries.py      Normalise source country codes to ISO alpha-3
        validation.py     Mandatory-field checks (incl. "NULL" text and blanks)
        deduplication.py  "Latest record wins" per member
        routing.py        Group current member records by country
        redemptions.py    Flatten the JSON redemption feed, one row per transaction
    tests/                pytest suite — the executable specification of every rule
    sql/
        01_raw_tables.sql          Layered schemas and raw landing tables
        02_load_raw.sql            Stage, file formats and COPY INTO loads
        03_staging.sql             Split, type, derive Age/Stale, record DQ reasons
        04_core_country_split.sql  MEMBER_CURRENT (SSOT) and generated country tables
        05_redemptions.sql         Flatten JSON, dedupe txn_id, join to members
        06_data_quality.sql        Data quality checks and layer reconciliation
    data/samples/         Sample input files used in tests and demos

### Sample data

`MEMBERS_20240101.txt` and the first record of `REDEMPTIONS_20240115.json` copy
the examples from the assessment PDF. `MEMBERS_20240102.txt` and the extra JSON
records are hand-made to exercise each known data issue:

| Sample row | What it exercises | Verified outcome |
| --- | --- | --- |
| Ravi (`223458`) in both member files | Member moves IND → USA | Only in `MEMBERS_USA` |
| Mike (`223460`) | 7-digit ambiguous date, `NULL` text DOB | Rejected: `INVALID_ENROLLMENT_DATE` |
| Member `223461` | Missing mandatory Member Name | Rejected: `MISSING_MEMBER_NAME` |
| Lena (`223462`) | Unknown country code `XYZ` | Rejected: `UNKNOWN_COUNTRY` |
| Omar (`223463`) | 11 fields instead of 10 | Rejected: `WRONG_FIELD_COUNT`, `INVALID_DOB` |
| Repeated `RX10091` | Duplicate transaction | Kept once |
| Member `223458` redemptions | Empty redemption list | No rows |
| Member `999999` | Orphan redemption | Excluded from the join; reported as `ORPHAN_REDEMPTION` |

Omar gets two reasons because the extra field shifts every later field, so the
post code lands in the DOB position. A wrong field count makes the rest of the
record untrustworthy.

## Approach

- **Python is the tested specification.** Every business rule is a small, pure
  function developed test-first.
- **SQL is the scaled implementation.** At billions of rows per day, row-by-row
  Python is not viable. The `sql/` scripts implement the same rules set-based in
  Snowflake (`COPY INTO`, `QUALIFY ROW_NUMBER()`, `LATERAL FLATTEN`).
- **Single Source of Truth.** `CORE.MEMBER_CURRENT` holds exactly one row per
  member: the latest valid record. Every country table is cut from it, so the
  country tables can never disagree, and a member can only be in one of them.
- **Country tables are generated, not hand-written.** A Snowflake Scripting block
  creates one `MEMBERS_<ISO>` table per entry in the `COUNTRY_CODE_MAP` reference
  table. Adding a country to the reference table adds its table on the next run.
- **Raw means as received.** Each member line lands whole in `RAW_LINE` and is
  split in staging, so a malformed row (wrong field count, wrong record type) is
  visible to validation instead of being reshaped or dropped at load. The JSON
  feed lands whole as `VARIANT`.
- **Nothing is silently dropped.** Rejected records stay in staging with their
  raw line and every rejection reason; the quarantine is
  `WHERE DQ_STATUS = 'REJECTED'`.
- **Lineage on every row.** `SOURCE_FILE_NAME` and `SOURCE_LINE_NUMBER` are
  captured at load and drive "latest record wins".
- **Rerunnable.** DDL uses `IF NOT EXISTS` / `CREATE OR REPLACE`; `COPY INTO`
  skips files it has already loaded, so a retried job does not duplicate rows.

Pipeline order:

    parse → validate → normalise country → derive Age/Stale → latest record wins → route

Routing happens after deduplication, so a member who moved country is routed
exactly once, to their current country.

### Production considerations

- **Storage:** the demo uses an internal stage. In production the stage would
  point at Azure Blob Storage; the `COPY` statements stay the same.
- **Incremental processing:** the demo rebuilds staging and `MEMBER_CURRENT` on
  every run for clarity. At billions of rows per day, staging would process only
  newly loaded files, and `MEMBER_CURRENT` would be updated with a `MERGE`.
- **Run parameters:** the business date is set with `SET RUN_BUSINESS_DATE` in
  the staging and DQ scripts. An orchestrator (e.g. Azure Data Factory) would
  pass it as a single job parameter instead.
- **Reference data:** country codes live in a table, so the business can add a
  country without a code release.

Known trade-off: rules exist in two places (Python and SQL). In production I
would test the SQL directly (e.g. dbt tests) and treat the Python as reference.

## Deliverables

| # | Deliverable | Status |
| --- | --- | --- |
| 1 | DDL for raw, staging and country target tables | Done and verified (`01`, `03`, `04`) |
| 2 | Staging with derived `Age` and `Stale_Member` | Done: tested in Python, verified in Snowflake (`03`) |
| 3 | Split into per-country tables, latest record wins | Done: tested in Python, verified in Snowflake (`04`) |
| 4 | Flatten JSON redemption feed and join to members | Done: tested in Python, verified in Snowflake (`05`) |
| 5 | Data validations | Done: rule checks, key uniqueness, orphans and layer reconciliation, verified in Snowflake (`06`) |
| 6 | Live demonstration | In preparation |

## Data quality checks

`CORE.DQ_ISSUES` collects every problem found in a run, one row per issue, with
the same columns for every check. **ERROR** means the record is held back;
**WARNING** means it is loaded but needs review.

| Check | Severity | What it catches |
| --- | --- | --- |
| `REJECTED_RECORD` | ERROR | Every staging rule failure, one row per reason, with file and line |
| `DUPLICATE_MEMBER_ID` | ERROR | More than one row per member in `MEMBER_CURRENT` |
| `DUPLICATE_TXN_ID` | ERROR | A transaction counted more than once |
| `ORPHAN_REDEMPTION` | WARNING | A redemption for a member we don't have |
| `SHORT_MEMBER_ID` | WARNING | Member ID shorter than 6 characters (possibly truncated) |
| `FLIGHT_BEFORE_ENROLLMENT` | WARNING | Last flight before enrollment |
| `DATE_AFTER_BUSINESS_DATE` | WARNING | DOB, enrollment or flight after the business date |
| `PARTNER_IS_PROGRAMME` | WARNING | `SkyPoints` listed as its own partner |
| `RAW_TO_STAGING_RECONCILE` | ERROR | Rows lost between raw and staging |
| `COUNTRY_TABLES_RECONCILE` | ERROR | Country tables don't add up to `MEMBER_CURRENT` |

Staging rule reasons: `WRONG_FIELD_COUNT`, `UNEXPECTED_RECORD_TYPE`,
`MISSING_MEMBER_NAME`, `MISSING_MEMBER_ID`, `MISSING_ENROLLMENT_DATE`,
`INVALID_ENROLLMENT_DATE`, `INVALID_LAST_FLIGHT_DATE`, `INVALID_DOB`,
`UNKNOWN_COUNTRY`, `MISSING_COUNTRY`, `FIELD_TOO_LONG`.

The reconciliation checks produce a row only when something is wrong. To prove
they are not silently broken, `COUNTRY_TABLES_RECONCILE` was tested by deleting
a row from `MEMBERS_USA`: the check reported `country tables 4 vs
MEMBER_CURRENT 5`, and cleared after the tables were rebuilt.

## Assumptions

| Topic | Decision | Reason |
| --- | --- | --- |
| Business key | `Member_ID`, not `Member_Name` | The spec marks Name as key, but names are not unique ("Mike" appears in both the AUS and USA samples). Treated as a documentation error. |
| File naming | `MEMBERS_YYYYMMDD.txt` and `REDEMPTIONS_YYYYMMDD.json` | The date in the name is the file's business date; the load ignores files that don't match. |
| "Latest record wins" | Latest by file business date (from filename); line order within the file breaks ties | `Last_Flight_Date` describes the member, not how recent the record is. |
| Rejected latest record | Only VALID records are ranked; a rejected newer record waits in quarantine | The member keeps their last known good state instead of disappearing from every country table. |
| Reference date for Age / Stale | A business date passed into the run, not `CURRENT_DATE` | Reruns are reproducible and tests are deterministic. |
| `Stale_Member` boundary | Stale only when days since flight is **> 90**; exactly 90 is not stale | Follows the spec literally. Verified: Omar's flight is exactly 90 days before the business date and shows `FALSE`. |
| Null `Last_Flight_Date` | `Stale_Member` is NULL (unknown) | Missing data is not evidence of staleness. |
| Unknown DOB | `Age` is NULL | No valid birth date means age is unknown, not zero. |
| Leap-day birthdays | A 29 Feb birthday counts as reached on 1 Mar in non-leap years | Common convention; the age calculation never constructs an invalid date. |
| Date format | Exactly 8 digits with an explicit format per column | Python's `strptime` silently guesses 7-digit dates (`1052022` → 5 Oct); strict length prevents that. |
| Post Code | Stored as VARCHAR, not INT | INT loses leading zeros; some countries (e.g. Canada) use alphanumeric codes. |
| Missing values | Empty, whitespace-only and the literal text `NULL` all count as missing | The AUS sample stores `NULL` as text. |
| Header records | Filtered out in staging, not rejected | Every file is expected to have one; it is not a data error. |
| Unknown country codes | Rejected for quarantine, never guessed | A member in the wrong country table is worse than a held record. |
| Missing country | Rejected with `MISSING_COUNTRY`, although Country is optional in the spec | A member without a country cannot be routed to a country table. |
| Target table naming | `MEMBERS_<ISO alpha-3>` (e.g. `MEMBERS_IND`) rather than `Table_India` | Derived directly from the normalised code; no second name mapping to maintain. |
| Short member IDs | Warning when shorter than 6 characters | Threshold taken from the sample, where full IDs have 6 digits; to be confirmed by the business. |
| Duplicate transactions | First occurrence of a `txn_id` is kept: within a feed in Python, across all feeds in Snowflake | Resent transactions must not double-count miles. |
| Members with no redemptions | Produce no redemption rows | `LATERAL FLATTEN ... OUTER => TRUE` would list them if the business wants that. |
| Unparseable records | Quarantined with a reason, never guessed | A wrong value is worse than a rejected one. |

## Known data issues in the samples

| # | Source | Issue | Handling |
| --- | --- | --- | --- |
| 1 | Spec vs sample | Spec defines 11 fields (incl. Post Code); header and detail rows have 10 | **Implemented:** rejected as `WRONG_FIELD_COUNT` (Python and SQL) |
| 2 | Spec | Member Name marked as key column | Use Member_ID (see Assumptions) |
| 3 | Intermediate table | DOB `03051985` became `3051985`: leading zero lost to an INT cast | **Implemented:** dates and IDs stay strings until explicitly parsed; raw layer is all text |
| 4 | Sample file | DOB is `MMDDYYYY`; other dates are `YYYYMMDD` | **Implemented:** each column parsed with its own explicit format |
| 5 | Intermediate table | Column named `County`; Agent_Name missing for 4 of 5 rows | **Implemented:** raw-to-staging and country-table reconciliation checks |
| 6 | Sample file | Country codes inconsistent: `PHIL` (4 chars), `AU` (2 chars) | **Implemented:** normalised to `PHL` / `AUS` via reference table; unknown codes rejected |
| 7 | Sample file | Member IDs `22345` and `2256` shorter than others | **Implemented:** `SHORT_MEMBER_ID` warning |
| 8 | AUS sample | Invalid date `2021-13-13`; literal string `NULL` | **Implemented:** impossible dates rejected; `NULL` text treated as missing |
| 9 | USA sample | Dates stored as numbers, e.g. `1052022`: ambiguous (1/05 or 10/5) | **Implemented:** rejected as `INVALID_ENROLLMENT_DATE`, never guessed |
| 10 | IND sample | Extra `Individual` column not in spec | Partly covered: an extra field in a detail record is rejected as `WRONG_FIELD_COUNT`. Validating the header row itself against the layout is planned. |
| 11 | IND sample | `3/5/2022`: day/month order ambiguous | **Implemented:** rejected by the strict 8-digit format |
| 12 | JSON feed | Partner `SkyPoints` is the programme itself; `PENDING` status; repeated `txn_id` | **Implemented:** duplicate `txn_id` kept once; `PARTNER_IS_PROGRAMME` warning. `PENDING` flagged for business clarification |
| 13 | Header line | Has the same field count as a detail record | **Implemented:** never treated as a member (Python rejects it; SQL filters it) |

## How I used AI

I used an AI assistant (Claude) as a pairing partner throughout. With a short
deadline, it drafted most of the test, implementation and SQL code; I ran every
Red → Green → Refactor cycle, ran every SQL script in Snowflake and checked the
results against expected values before committing, and made sure I can explain
every line.

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
- **Revised a design:** The first raw table split each line into columns at load.
  We changed it to land whole lines after realising that column-splitting could
  silently drop the extra field in an 11-field row.
- **Verified, not assumed:** The expected raw row count I worked from (13) was
  wrong; Snowflake returned 12. I checked the sample files, confirmed 12 was
  correct (2 headers + 10 detail lines) and corrected the documentation.
- **Tested the tests:** The reconciliation checks returned no rows, which could
  mean "passing" or "broken". I deleted a row from `MEMBERS_USA` on purpose,
  confirmed `COUNTRY_TABLES_RECONCILE` reported the mismatch, then rebuilt the
  tables and confirmed it cleared.

<!-- Keep adding entries: what you asked, what you accepted, what you rejected and why. -->

## Open questions for the business

- Should `PENDING` redemptions count towards a member's mileage balance?
- Is `SkyPoints` a valid partner value in the redemption feed?
- If a resent transaction differs from the original (e.g. `PENDING` then
  `COMPLETED`), which version is correct?
- What is the date format convention for each country's source system? (The AUS
  sheet uses `YYYY-MM-DD`, which the compact 8-digit parser would reject.)
- Is a short Member ID such as `2256` valid, or truncated upstream? Is 6 the
  right minimum length?
- Should members with no redemptions appear in the redemption output?
