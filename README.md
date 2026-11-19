# SkyPoints ETL — Member Profile & Redemption Pipeline

Incubyte Data Engineer technical assessment.

> **Status:** In progress. Built incrementally with Test-Driven Development;
> the commit history shows how the solution evolved.

## Problem

SkyPoints receives two daily feeds from its source system:

1. A pipe-delimited flat file of member profiles (header + detail records)
2. A JSON feed of partner-airline mileage redemptions

The pipeline must load these into raw → staging → country-specific target
tables, derive `Age` and `Stale_Member`, apply a "latest record wins" rule when
a member moves country, flatten the redemption feed, and validate data quality —
at a scale of billions of records per day.

## Setup

Requires Python 3.10+.

    python3 -m venv .venv
    source .venv/bin/activate
    pip install pytest

## Running tests

    pytest

## Project structure

    src/skypoints/   Pure-Python rule engine (parsing, validation, derivations)
    tests/           pytest suite — the executable specification of every rule
    sql/             Snowflake DDL and set-based transformation scripts
    data/samples/    Sample input files used in tests and demos

## Approach

- **Python is the tested specification.** Every business rule (parsing,
  validation, Age, Stale_Member, latest-record-wins, JSON flattening) is a pure
  function developed test-first.
- **SQL is the scaled implementation.** At billions of rows per day, row-by-row
  Python is not viable. The `sql/` scripts implement the same rules set-based in
  Snowflake (`COPY INTO`, `QUALIFY ROW_NUMBER()`, `LATERAL FLATTEN`).
- **Single Source of Truth.** One conformed `member_current` table holds the
  latest record per member. Country tables are derived from it, generated from a
  country list rather than hand-written per country.

Known trade-off: rules exist in two places (Python and SQL). In production I
would test the SQL directly (e.g. dbt tests) and treat the Python as reference.

## Assumptions

| Topic | Decision | Reason |
| --- | --- | --- |
| Business key | `Member_ID`, not `Member_Name` | The spec marks Name as key, but names are not unique ("Mike" appears in both the AUS and USA samples). Treated as a documentation error. |
| "Latest record wins" | Latest by file business date (from filename); record order within the file breaks ties | `Last_Flight_Date` describes the member, not how recent the record is. |
| Reference date for Age / Stale | A business date passed into the run, not `CURRENT_DATE` | Reruns are reproducible and tests are deterministic. |
| `Stale_Member` boundary | Stale only when days since flight is **> 90**; exactly 90 is not stale | Follows the spec literally. |
| Null `Last_Flight_Date` | `Stale_Member` is NULL (unknown) | Missing data is not evidence of staleness. |
| Post Code | Stored as VARCHAR, not INT | INT loses leading zeros; some countries (e.g. Canada) use alphanumeric codes. |
| Unparseable dates | Quarantined, never guessed | A wrong date is worse than a rejected one. |

## Known data issues in the samples

| # | Source | Issue | Handling |
| --- | --- | --- | --- |
| 1 | Spec vs sample | Spec defines 11 fields (incl. Post Code); header and detail rows have 10 | Validate field count against the header |
| 2 | Spec | Member Name marked as key column | Use Member_ID (see Assumptions) |
| 3 | Intermediate table | DOB `03051985` became `3051985` — leading zero lost to an INT cast | Keep dates/IDs as strings until explicitly parsed |
| 4 | Sample file | DOB is `MMDDYYYY`; other dates are `YYYYMMDD` | Parse each column with its own explicit format |
| 5 | Intermediate table | Column named `County`; Agent_Name missing for 4 of 5 rows | Raw-to-staging reconciliation check |
| 6 | Sample file | Country codes inconsistent: `PHIL` (4 chars), `AU` (2 chars) | Normalise to ISO alpha-3; unknown codes quarantined |
| 7 | Sample file | Member IDs `22345` and `2256` shorter than others | Flagged as a warning (valid per spec, but possibly truncated) |
| 8 | AUS sample | Invalid date `2021-13-13`; literal string `NULL` | Date validation; treat sentinel strings as null |
| 9 | USA sample | Dates stored as numbers, e.g. `1052022` — ambiguous (1/05 or 10/5) | Rejected: cannot be parsed safely |
| 10 | IND sample | Extra `Individual` column not in spec | Header/schema validation |
| 11 | IND sample | `3/5/2022` — day/month order ambiguous | Explicit format per source; reject if ambiguous |
| 12 | JSON feed | Partner `SkyPoints` is the programme itself; `PENDING` status | Flagged for business clarification; dedupe on `txn_id` |

## How I used AI

I used an AI assistant (Claude) as a reviewer and pairing partner, not as a code
generator.

- **Analysis:** Asked it to review the spec and samples for data issues and
  ambiguities. I verified each finding against the source files myself before
  recording it above.
- **Coding:** Wrote tests and implementations myself in Red → Green → Refactor
  steps, using the assistant to review each step.

<!-- Keep adding entries: what you asked, what you accepted, what you rejected and why. -->

## Open questions for the business

- Should `PENDING` redemptions count towards a member's mileage balance?
- Is `SkyPoints` a valid partner value in the redemption feed?
- What is the date format convention for each country's source system?
