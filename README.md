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

## Running the SQL (Snowflake)

Run the scripts in `sql/` in numeric order in a Snowflake worksheet with a
warehouse selected:

1. `01_raw_tables.sql` creates the database, the RAW / STAGING / CORE schemas
   and the raw landing tables.
2. Upload the files in `data/samples/` to the stage `SKYPOINTS.RAW.SKYPOINTS_LANDING`.
3. `02_load_raw.sql` creates the stage and file formats and loads the files.

Expected after step 3: 13 rows in `MEMBER_PROFILE_RAW` (2 headers + 11 detail
lines) and 3 rows in `REDEMPTION_FEED_RAW`.

> The SQL scripts are written but **not yet verified in Snowflake**.

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
        01_raw_tables.sql Layered schemas and raw landing tables
        02_load_raw.sql   Stage, file formats and COPY INTO loads
    data/samples/         Sample input files used in tests and demos

### Sample data

`MEMBERS_20240101.txt` and the first record of `REDEMPTIONS_20240115.json` copy
the examples from the assessment PDF. `MEMBERS_20240102.txt` and the extra JSON
records are hand-made to exercise each known data issue:

| Sample row | What it exercises |
| --- | --- |
| Ravi (`223458`) in both member files | Member moves IND → USA; latest record wins |
| Mike (`223460`) | 7-digit ambiguous date and `NULL` text DOB |
| Member `223461` | Missing mandatory Member Name |
| Lena (`223462`) | Unknown country code `XYZ` |
| Omar (`223463`) | 11 fields instead of 10 |
| Repeated `RX10091` | Duplicate transaction in the redemption feed |
| Member `223458` redemptions | Empty redemption list |
| Member `999999` | Orphan redemption with no matching member |

## Approach

- **Python is the tested specification.** Every business rule is a small, pure
  function developed test-first.
- **SQL is the scaled implementation.** At billions of rows per day, row-by-row
  Python is not viable. The `sql/` scripts implement the same rules set-based in
  Snowflake (`COPY INTO`, `QUALIFY ROW_NUMBER()`, `LATERAL FLATTEN`).
- **Single Source of Truth.** One conformed `member_current` table holds the
  latest record per member. Country tables are derived from it, generated from a
  country list rather than hand-written per country.
- **Raw means as received.** Each member line lands whole in `RAW_LINE` and is
  split in staging, so a malformed row (wrong field count, wrong record type) is
  visible to validation instead of being reshaped or dropped at load. The JSON
  feed lands whole as `VARIANT`.
- **Lineage on every row.** `SOURCE_FILE_NAME` and `SOURCE_LINE_NUMBER` are
  captured at load and drive "latest record wins".
- **Rerunnable.** DDL uses `IF NOT EXISTS`; `COPY INTO` skips files it has already
  loaded, so a retried job does not duplicate rows.
- **Production storage.** The demo uses an internal stage. In production the
  stage would point at Azure Blob Storage; the `COPY` statements stay the same.

Pipeline order:

    parse → validate → normalise country → derive Age/Stale → latest record wins → route

Routing happens after deduplication, so a member who moved country is routed
exactly once, to their current country.

Known trade-off: rules exist in two places (Python and SQL). In production I
would test the SQL directly (e.g. dbt tests) and treat the Python as reference.

## Deliverables

| # | Deliverable | Status |
| --- | --- | --- |
| 1 | DDL for raw, staging and country target tables | Raw tables and load written; staging and targets planned |
| 2 | Staging with derived `Age` and `Stale_Member` | Rules implemented and tested in Python; SQL planned |
| 3 | Split into per-country tables, latest record wins | Rules implemented and tested in Python; SQL planned |
| 4 | Flatten JSON redemption feed and join to members | Flattening implemented and tested in Python; SQL and join planned |
| 5 | Data validations | Field count, record type, dates, mandatory fields, country codes, duplicate transactions done; more planned |
| 6 | Live demonstration | Planned |

## Assumptions

| Topic | Decision | Reason |
| --- | --- | --- |
| Business key | `Member_ID`, not `Member_Name` | The spec marks Name as key, but names are not unique ("Mike" appears in both the AUS and USA samples). Treated as a documentation error. |
| File naming | `MEMBERS_YYYYMMDD.txt` and `REDEMPTIONS_YYYYMMDD.json` | The date in the name is the file's business date; the load ignores files that don't match. |
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
| Duplicate transactions | The first occurrence of a `txn_id` within a feed is kept | Resent transactions must not double-count miles. Cross-day duplicates are handled in Snowflake. |
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
| 12 | JSON feed | Partner `SkyPoints` is the programme itself; `PENDING` status; repeated `txn_id` | **Implemented:** duplicate `txn_id` kept once per feed. Partner and status flagged for business clarification |
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
- **Revised a design:** The first raw table split each line into columns at load.
  We changed it to land whole lines after realising that column-splitting could
  silently drop the extra field in an 11-field row.

<!-- Keep adding entries: what you asked, what you accepted, what you rejected and why. -->

## Open questions for the business

- Should `PENDING` redemptions count towards a member's mileage balance?
- Is `SkyPoints` a valid partner value in the redemption feed?
- If a resent transaction differs from the original (e.g. `PENDING` then
  `COMPLETED`), which version is correct?
- What is the date format convention for each country's source system? (The AUS
  sheet uses `YYYY-MM-DD`, which the compact 8-digit parser would reject.)
- Is a short Member ID such as `2256` valid, or truncated upstream?
