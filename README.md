# SkyPoints ETL — Member Profile & Redemption Pipeline

Incubyte Data Engineer technical assessment.

> **Status:** All five written deliverables are implemented. Business rules are
> developed test-first in Python; the same rules run set-based in Snowflake and
> have been verified against the sample data. The three country datasets
> provided with the assessment (`AUS.xlsx`, `USA.csv`, `IND.csv`) are read,
> standardised and validated by tested Python code. The commit history shows how
> the solution evolved, one Red → Green → Refactor cycle at a time.

## Problem

SkyPoints receives two daily feeds from its source system:

1. A pipe-delimited flat file of member profiles (header + detail records)
2. A JSON feed of partner-airline mileage redemptions

The pipeline must load these into raw → staging → country-specific target
tables, derive `Age` and `Stale_Member`, apply a "latest record wins" rule when
a member moves country, flatten the redemption feed, and validate data quality —
at a scale of billions of records per day.

The assessment also provides three per-country member datasets with their own
layouts and data quality problems.

## Setup

Requires Python 3.9+. One runtime dependency, `openpyxl`, because one of the
provided source files is an Excel workbook.

    python3 -m venv .venv
    source .venv/bin/activate
    pip install pytest openpyxl

## Running tests

    pytest

## Running the Python pipeline (pipe-delimited feed)

    PYTHONPATH=src python3 -m skypoints.pipeline

Reads the member files in `data/samples/`, prints current members by country and
the quarantined records with their reasons. The result matches the Snowflake
output for the same files.

## Processing the provided country files

    PYTHONPATH=src python3 -m skypoints.sources

Reads `data/provided/AUS.xlsx`, `USA.csv` and `IND.csv`, maps each file's columns
to the standard fields, and splits the rows into readable members and a
quarantine. Verified output:

    Readable members (5):
      AUS-1: Mike
      AUS-3: Cristina
      IND-3: Sameer
      USA-1: Sam
      USA-3: Mike

    Quarantined (4):
      AUS-2 (AUS.xlsx): INVALID_ENROLLMENT_DATE
      IND-1 (IND.csv): AMBIGUOUS_DOB
      IND-2 (IND.csv): AMBIGUOUS_ENROLLMENT_DATE, AMBIGUOUS_LAST_FLIGHT_DATE
      USA-2 (USA.csv): AMBIGUOUS_ENROLLMENT_DATE, AMBIGUOUS_LAST_FLIGHT_DATE

The two members named Mike (`AUS-1`, `USA-3`) stay separate people: each file
numbers its members from 1, so the key is country + source ID.

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
| 8 | Run `06_data_quality.sql` | `DQ_ISSUES`: REJECTED_RECORD 5, ORPHAN_REDEMPTION 1, PARTNER_IS_PROGRAMME 1, RESENT_TXN_ID 1, SHORT_MEMBER_ID 2 |

Running step 2 twice is intentional and safe: `IF NOT EXISTS` makes the DDL a
no-op the second time, and `COPY INTO` skips files it has already loaded.

`MEMBERS_IND` being empty is the proof of "latest record wins": Ravi was Indian
in the first file and moved to the USA in the second.

## Project structure

    src/skypoints/
        parsing.py        Split a pipe-delimited detail record into named fields
        dates.py          Strict date parsing for the spec's 8-digit formats
        derivations.py    Age and Stale_Member, computed as of a business date
        countries.py      Normalise source country codes to ISO alpha-3
        validation.py     Mandatory-field checks (incl. "NULL" text and blanks)
        deduplication.py  "Latest record wins" per member
        routing.py        Group current member records by country
        redemptions.py    Flatten the JSON redemption feed, one row per transaction
        pipeline.py       Runs the pipe-feed rules end to end over the sample files
        source_dates.py   Reads messy source dates; accepts only unambiguous ones
        sources.py        Reads the provided CSV/Excel country files into standard fields
    tests/                pytest suite — the executable specification of every rule
    sql/
        01_raw_tables.sql          Layered schemas and raw landing tables
        02_load_raw.sql            Stage, file formats and COPY INTO loads
        03_staging.sql             Split, type, derive Age/Stale, record DQ reasons
        04_core_country_split.sql  MEMBER_CURRENT (SSOT) and generated country tables
        05_redemptions.sql         Flatten JSON, dedupe txn_id, join to members
        06_data_quality.sql        Data quality checks and layer reconciliation
    data/provided/        The three country datasets supplied with the assessment, unchanged
    data/samples/         Pipe-delimited and JSON feeds used in tests and demos

### Provided country datasets

Committed exactly as received. Each file has its own layout:

| Standard field | `AUS.xlsx` | `USA.csv` | `IND.csv` |
| --- | --- | --- | --- |
| `source_id` | Unique ID | ID | ID |
| `member_name` | Member Name | Name | Name |
| `tier_code` | Tier Type | TierCode | TierCode |
| `dob` | Date of Birth | — | DOB |
| `enrollment_date` | Date of Enrollment | EnrollmentDate | EnrollmentDate |
| `last_flight_date` | Date of Flight | FlightDate | Flight Date |
| `member_type` | — | — | Individual or Corporate |

The mapping lives in one dictionary (`SOURCE_COLUMNS`), so a new country needs a
new entry, not new code. A file whose columns don't match its layout is rejected
with an error naming the missing and unexpected columns.

### Sample data

`MEMBERS_20240101.txt` and the first record of `REDEMPTIONS_20240115.json` copy
the examples from the assessment PDF. `MEMBERS_20240102.txt` and the extra JSON
records are hand-made to exercise each known data issue in the pipe-delimited
format:

| Sample row | What it exercises | Verified outcome |
| --- | --- | --- |
| Ravi (`223458`) in both member files | Member moves IND → USA | Only in `MEMBERS_USA` |
| Mike (`223460`) | 7-digit date, `NULL` text DOB | Rejected: `INVALID_ENROLLMENT_DATE` |
| Member `223461` | Missing mandatory Member Name | Rejected: `MISSING_MEMBER_NAME` |
| Lena (`223462`) | Unknown country code `XYZ` | Rejected: `UNKNOWN_COUNTRY` |
| Omar (`223463`) | 11 fields instead of 10 | Rejected: `WRONG_FIELD_COUNT`, `INVALID_DOB` |
| Repeated `RX10091` | Resent transaction | Kept once; reported as `RESENT_TXN_ID` |
| Member `223458` redemptions | Empty redemption list | No rows |
| Member `999999` | Orphan redemption | Excluded from the join; reported as `ORPHAN_REDEMPTION` |

Omar gets two reasons in SQL because the extra field shifts every later field, so
the post code lands in the DOB position. A wrong field count makes the rest of
the record untrustworthy.

## Approach

- **Python is the tested specification.** Every business rule is a small, pure
  function developed test-first. Known differences from the SQL are listed below.
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
  feed lands whole as `VARIANT`. The provided datasets are committed unchanged.
- **Never guess.** A value that can be read more than one way is quarantined with
  a reason, not resolved by assumption.
- **Nothing is silently dropped.** Rejected records stay in staging with their
  raw line and every rejection reason; the quarantine is
  `WHERE DQ_STATUS = 'REJECTED'`. Filters use `IS DISTINCT FROM` so a `NULL`
  value can never make a row disappear.
- **One bad record never stops a run.** Every rejection raises `ValueError` (or a
  subclass), which the pipeline turns into a quarantine reason.
- **Lineage on every row.** `SOURCE_FILE_NAME` and `SOURCE_LINE_NUMBER` are
  captured at load and drive "latest record wins".
- **Rerunnable and deterministic.** DDL uses `IF NOT EXISTS` / `CREATE OR
  REPLACE`; `COPY INTO` skips files it has already loaded, so a retried job does
  not duplicate rows; every ranking has a final tie-breaker, so the same input
  always gives the same output.

Pipeline order:

    parse → validate → normalise country → derive Age/Stale → latest record wins → route

Routing happens after deduplication, so a member who moved country is routed
exactly once, to their current country.

### Python vs SQL: known differences

| Area | Python | SQL |
| --- | --- | --- |
| Malformed pipe record | One reason, `MALFORMED_RECORD`; the parser stops at the first structural problem | Separate `WRONG_FIELD_COUNT` / `UNEXPECTED_RECORD_TYPE`, and later columns are still evaluated |
| Field length check | Not implemented | `FIELD_TOO_LONG` |
| Missing country | Reported as `UNKNOWN_COUNTRY` | Separate `MISSING_COUNTRY` |
| Whitespace around values | Kept as received in the pipe feed | Trimmed in staging |
| Provided CSV/Excel files | Read and validated (`sources.py`) | Not loaded; see production considerations |
| Redemption join and checks | Flattening only (`redemptions.py`), not part of `pipeline.py` | Flatten, cross-feed dedupe, join, `ORPHAN_REDEMPTION`, `RESENT_TXN_ID`, `INVALID_REDEMPTION` |
| Cross-layer reconciliation | Not applicable | `RAW_TO_STAGING_RECONCILE`, `COUNTRY_TABLES_RECONCILE` |

Both reject the same records on the sample data; they differ only in how finely
the reasons are reported. Snowflake is the system of record at scale, so the
cross-layer checks (reconciliation, joins, orphans) live there by design.

### Production considerations

- **Storage:** the demo uses an internal stage. In production the stage would
  point at Azure Blob Storage; the `COPY` statements stay the same.
- **Excel sources:** Snowflake `COPY INTO` does not read `.xlsx`. In production,
  the landing step (e.g. an Azure Data Factory copy activity) would convert
  workbooks to CSV or Parquet, and staging would apply the same per-country column
  mapping as `SOURCE_COLUMNS`.
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
| 4 | Flatten JSON redemption feed and join to members | Done: flattening tested in Python; flatten and join verified in Snowflake (`05`) |
| 5 | Data validations | Done: rule checks, key uniqueness, redemption checks, orphans and layer reconciliation in Snowflake (`06`); provided country files validated in Python (`sources.py`) |
| 6 | Live demonstration | In preparation |

## Data quality checks

`CORE.DQ_ISSUES` collects every problem found in a run, one row per issue, with
the same columns for every check. **ERROR** means the record is held back;
**WARNING** means it is loaded but needs review.

| Check | Severity | What it catches |
| --- | --- | --- |
| `REJECTED_RECORD` | ERROR | Every staging rule failure, one row per reason, with file and line |
| `DUPLICATE_MEMBER_ID` | ERROR | More than one row per member in `MEMBER_CURRENT` |
| `DUPLICATE_TXN_ID` | ERROR | A transaction held more than once in staging (guards the dedupe) |
| `RESENT_TXN_ID` | WARNING | The same transaction received more than once; staging keeps the first copy |
| `INVALID_REDEMPTION` | ERROR | A transaction with a missing ID or status, an invalid date, or miles that are not a positive number; checked on the raw feed so dedupe cannot hide it |
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

Provided-file reasons: `MISSING_<FIELD>` (source ID, member name or enrollment
date is blank), `AMBIGUOUS_<FIELD>` (the text is a valid date under more than one
reading) and `INVALID_<FIELD>` (no valid reading, or an unrecognised format).

Checks produce a row only when something is wrong, so an empty result could mean
"passing" or "broken". Each check that stays silent on the sample data was
proven by breaking the data on purpose:

- `COUNTRY_TABLES_RECONCILE`: deleting a row from `MEMBERS_USA` reported
  `country tables 4 vs MEMBER_CURRENT 5`, and cleared after the tables were rebuilt.
- NULL-safe staging: an empty raw line and a line without delimiters were both
  kept and rejected with `WRONG_FIELD_COUNT` and `UNEXPECTED_RECORD_TYPE`.
- `INVALID_REDEMPTION`: a transaction with no ID, an impossible date, negative
  miles and no status was reported with all four problems.

## Assumptions

| Topic | Decision | Reason |
| --- | --- | --- |
| Business key (pipe feed) | `Member_ID`, not `Member_Name` | The spec marks Name as key, but names are not unique (two different members called Mike exist in the provided files). Treated as a documentation error and listed as an open question. |
| Business key (provided files) | Country + source ID (e.g. `AUS-1`) | Each file numbers its members from 1, so the same ID belongs to different people in different countries. |
| Country of a provided file | Taken from the file name (`AUS.xlsx` → `AUS`) | None of the files has a country column. |
| Mandatory fields (provided files) | Source ID, member name and enrollment date | The same fields the spec marks as mandatory, with the file's ID standing in for Member ID. |
| File naming (pipe feed) | `MEMBERS_YYYYMMDD.txt` and `REDEMPTIONS_YYYYMMDD.json` | The date in the name is the file's business date; the load ignores files that don't match. |
| "Latest record wins" | Latest by file business date (from filename); line order within the file breaks ties; file name is the final tie-breaker in SQL | `Last_Flight_Date` describes the member, not how recent the record is. The final tie-breaker keeps the result deterministic. |
| Rejected latest record | Only VALID records are ranked; a rejected newer record waits in quarantine | The member keeps their last known good state instead of disappearing from every country table. |
| Reference date for Age / Stale | A business date passed into the run, not `CURRENT_DATE` | Reruns are reproducible and tests are deterministic. |
| `Stale_Member` boundary | Stale only when days since flight is **> 90**; exactly 90 is not stale | Follows the spec literally. Verified: Omar's flight is exactly 90 days before the business date and shows `FALSE`. |
| Null `Last_Flight_Date` | `Stale_Member` is NULL (unknown) | Missing data is not evidence of staleness. |
| Unknown DOB | `Age` is NULL; a blank DOB is not an error | DOB is optional. No valid birth date means age is unknown, not zero. |
| Leap-day birthdays | A 29 Feb birthday counts as reached on 1 Mar in non-leap years | Common convention; the age calculation never constructs an invalid date. |
| Dates in the pipe feed | Exactly 8 digits with an explicit format per column | Python's `strptime` silently guesses 7-digit dates (`1052022` → 5 Oct); strict length prevents that. |
| Dates in the provided files | Accepted only when every possible reading gives the same day; otherwise `AMBIGUOUS_<FIELD>` | Day-first and month-first conventions differ by country and are not confirmed. Accepting only unambiguous dates keeps valid data (e.g. `6152022`) without ever guessing. Switching to a confirmed per-country convention would be a configuration change. |
| Excel date cells | Trusted as stored | Excel stores real dates without day/month ambiguity; only text cells are parsed. |
| Post Code | Stored as VARCHAR, not INT | INT loses leading zeros; some countries (e.g. Canada) use alphanumeric codes. |
| Missing values | Empty, whitespace-only, the literal text `NULL`, and empty Excel cells all count as missing | The AUS file stores `NULL` as text. |
| Header records | Filtered out in staging, not rejected | Every file is expected to have one; it is not a data error. |
| Unknown country codes | Rejected for quarantine, never guessed | A member in the wrong country table is worse than a held record. |
| Missing country | Rejected with `MISSING_COUNTRY` in SQL, although Country is optional in the spec | A member without a country cannot be routed to a country table. |
| Target table naming | `MEMBERS_<ISO alpha-3>` (e.g. `MEMBERS_IND`) rather than `Table_India` | Derived directly from the normalised code; no second name mapping to maintain. |
| Short member IDs | Warning when shorter than 6 characters | Threshold taken from the sample, where full IDs have 6 digits; to be confirmed by the business. |
| Duplicate transactions | First occurrence of a `txn_id` is kept: within a feed in Python, across all feeds in Snowflake; resends are reported as `RESENT_TXN_ID` | Resent transactions must not double-count miles, but the business should still see that they happened. |
| Members with no redemptions | Produce no redemption rows | `LATERAL FLATTEN ... OUTER => TRUE` would list them if the business wants that. |
| Unparseable records | Quarantined with a reason, never guessed | A wrong value is worse than a rejected one. |

## Known data issues

| # | Source | Issue | Handling |
| --- | --- | --- | --- |
| 1 | Spec vs sample | Spec defines 11 fields (incl. Post Code); header and detail rows have 10 | **Implemented:** rejected (`MALFORMED_RECORD` in Python, `WRONG_FIELD_COUNT` in SQL) |
| 2 | Spec | Member Name marked as key column | Use Member_ID (see Assumptions); open question |
| 3 | Intermediate table | DOB `03051985` became `3051985`: leading zero lost to an INT cast | **Implemented:** dates and IDs stay strings until explicitly parsed; raw layer is all text |
| 4 | Sample file | DOB is `MMDDYYYY`; other dates are `YYYYMMDD` | **Implemented:** each column parsed with its own explicit format |
| 5 | Intermediate table | Column named `County`; Agent_Name missing for 4 of 5 rows | **Implemented:** raw-to-staging and country-table reconciliation checks |
| 6 | Sample file | Country codes inconsistent: `PHIL` (4 chars), `AU` (2 chars) | **Implemented:** normalised to `PHL` / `AUS` via reference table; unknown codes rejected |
| 7 | Sample file | Member IDs `22345` and `2256` shorter than others | **Implemented:** `SHORT_MEMBER_ID` warning |
| 8 | `AUS.xlsx` | Date column mixes real Excel dates with the text `2021-13-13` (impossible month); DOB is the text `NULL` | **Implemented:** `INVALID_ENROLLMENT_DATE`; `NULL` treated as missing |
| 9 | `USA.csv` | Dates stored as numbers with the leading zero lost. `6152022` and `8202022` have one valid reading; `1052022` has four (Jan 5, Oct 5, May 1, May 10) and `1152022` three | **Implemented:** unambiguous values recovered; ambiguous ones quarantined as `AMBIGUOUS_*`. No DOB column |
| 10 | `IND.csv` | Extra `Individual or Corporate` column; different column order | **Implemented:** mapped to `member_type` by the per-country column map |
| 11 | `IND.csv` | Text dates without leading zeros: `12/1/1998`, `3/5/2022` and `3/10/2022` are valid both day-first and month-first | **Implemented:** quarantined as `AMBIGUOUS_*`; unambiguous ones such as `8/13/1982` accepted |
| 12 | All provided files | Different column names per file; no country column; IDs `1`–`3` repeated in every country | **Implemented:** per-country column map, country from file name, key = country + source ID; blank mandatory fields reported as `MISSING_*`; unexpected layouts rejected |
| 13 | JSON feed | Partner `SkyPoints` is the programme itself; `PENDING` status; repeated `txn_id` | **Implemented:** duplicate `txn_id` kept once and reported as `RESENT_TXN_ID`; `PARTNER_IS_PROGRAMME` warning. `PENDING` flagged for business clarification |
| 14 | Header line | Has the same field count as a detail record | **Implemented:** never treated as a member (Python rejects it; SQL filters it) |
| 15 | Any input file | Blank lines or lines without delimiters | **Implemented:** rejected as malformed in Python instead of crashing; kept and rejected in SQL (`IS DISTINCT FROM`, so a `NULL` record type is never silently filtered out) |

## How I used AI

I used AI tools deliberately to move faster, while keeping every decision and
every line of code my own responsibility. AI drafted code and suggested
approaches; I worked in strict Red → Green → Refactor cycles, ran every SQL
script in Snowflake against expected results, and only committed what I had
verified and could explain.

- **Verified every finding against the source.** AI helped list potential data
  issues in the spec and datasets; I checked each one against the actual files,
  including the raw cell values in the provided spreadsheets, before recording it.
- **Proved claims with failing tests.** AI pointed out that Python's `strptime`
  silently parses the ambiguous `1052022` as 5 October. I confirmed this with a
  failing test before making date parsing strict.
- **Kept scope tight.** I rejected suggestions that no test required (e.g. a
  digits-only date check) to avoid untested code.
- **Changed a design when the evidence required it.** The first raw table split
  each line into columns at load. I changed it to land whole lines after seeing
  that column-splitting could silently drop the extra field in an 11-field row.
- **Tested the tests.** Checks that return no rows could be passing or broken, so
  I broke the data on purpose for each one (see Data quality checks) and confirmed
  it reported the problem, then restored the data and confirmed it cleared.
- **Used AI as a critical reviewer.** I asked a second AI to review the
  repository as a sceptical interviewer would. It found an edge case where a
  blank line raised an uncaught `IndexError`, blank mandatory fields being
  accepted in the provided files, and a SQL `NULL` comparison that could silently
  drop malformed rows. I reproduced each one with a failing test or a deliberately
  broken row before fixing it.

<!-- Keep adding entries: what you asked, what you accepted, what you rejected and why. -->

## Open questions for the business

- The spec marks Member Name as the key column, but names are not unique. Is
  Member ID the intended key?
- What date convention does each country's source system use (day-first or
  month-first)? Confirming it would let ambiguous dates such as `3/5/2022` and
  `1052022` be loaded instead of quarantined.
- How do the IDs in the provided country files relate to the `Member_ID` in the
  pipe-delimited feed?
- What does `Individual or Corporate` mean for the business, and should other
  countries supply it too?
- Should `PENDING` redemptions count towards a member's mileage balance?
- Is `SkyPoints` a valid partner value in the redemption feed?
- If a resent transaction differs from the original (e.g. `PENDING` then
  `COMPLETED`), which version is correct?
- Is a short Member ID such as `2256` valid, or truncated upstream? Is 6 the
  right minimum length?
- Should members with no redemptions appear in the redemption output?
