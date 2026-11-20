USE SCHEMA SKYPOINTS.STAGING;

-- The business date for this run. Age and Stale are computed as of this date, never CURRENT_DATE.
SET RUN_BUSINESS_DATE = '2024-01-15';

-- Reference data, not code: the business can add a country without a release.
CREATE OR REPLACE TABLE COUNTRY_CODE_MAP (
    SOURCE_CODE  VARCHAR,
    ISO_ALPHA3   VARCHAR(3)
);
INSERT INTO COUNTRY_CODE_MAP VALUES
    ('USA', 'USA'), ('IND', 'IND'), ('CAN', 'CAN'), ('PHIL', 'PHL'), ('AU', 'AUS');

CREATE OR REPLACE TABLE MEMBER_PROFILE_STG AS
WITH split_lines AS (
    SELECT
        SPLIT(RAW_LINE, '|')                                                  AS parts,
        RAW_LINE,
        SOURCE_FILE_NAME,
        SOURCE_LINE_NUMBER,
        TO_DATE(REGEXP_SUBSTR(SOURCE_FILE_NAME, '[0-9]{8}'), 'YYYYMMDD')     AS FILE_BUSINESS_DATE
    FROM SKYPOINTS.RAW.MEMBER_PROFILE_RAW
),
fields AS (
    -- Blank, whitespace-only and the text 'NULL' all become real NULLs.
    SELECT
        parts[1]::VARCHAR                                          AS RECORD_TYPE,
        ARRAY_SIZE(parts) - 2                                      AS FIELD_COUNT,
        NULLIF(NULLIF(TRIM(parts[2]::VARCHAR), ''), 'NULL')        AS MEMBER_NAME,
        NULLIF(NULLIF(TRIM(parts[3]::VARCHAR), ''), 'NULL')        AS MEMBER_ID,
        NULLIF(NULLIF(TRIM(parts[4]::VARCHAR), ''), 'NULL')        AS ENROLLMENT_DATE_RAW,
        NULLIF(NULLIF(TRIM(parts[5]::VARCHAR), ''), 'NULL')        AS LAST_FLIGHT_DATE_RAW,
        NULLIF(NULLIF(TRIM(parts[6]::VARCHAR), ''), 'NULL')        AS TIER_CODE,
        NULLIF(NULLIF(TRIM(parts[7]::VARCHAR), ''), 'NULL')        AS AGENT_NAME,
        NULLIF(NULLIF(TRIM(parts[8]::VARCHAR), ''), 'NULL')        AS STATE,
        NULLIF(NULLIF(TRIM(parts[9]::VARCHAR), ''), 'NULL')        AS COUNTRY_RAW,
        NULLIF(NULLIF(TRIM(parts[10]::VARCHAR), ''), 'NULL')       AS DOB_RAW,
        NULLIF(NULLIF(TRIM(parts[11]::VARCHAR), ''), 'NULL')       AS IS_ACTIVE,
        RAW_LINE, SOURCE_FILE_NAME, SOURCE_LINE_NUMBER, FILE_BUSINESS_DATE
    FROM split_lines
),
typed AS (
    -- Strict: exactly 8 characters, explicit format per column. Anything else stays NULL and is flagged.
    SELECT
        f.*,
        IFF(LENGTH(ENROLLMENT_DATE_RAW) = 8, TRY_TO_DATE(ENROLLMENT_DATE_RAW, 'YYYYMMDD'), NULL)    AS ENROLLMENT_DATE,
        IFF(LENGTH(LAST_FLIGHT_DATE_RAW) = 8, TRY_TO_DATE(LAST_FLIGHT_DATE_RAW, 'YYYYMMDD'), NULL)  AS LAST_FLIGHT_DATE,
        IFF(LENGTH(DOB_RAW) = 8, TRY_TO_DATE(DOB_RAW, 'MMDDYYYY'), NULL)                           AS DOB,
        m.ISO_ALPHA3                                                                                AS COUNTRY
    FROM fields f
    LEFT JOIN COUNTRY_CODE_MAP m ON m.SOURCE_CODE = f.COUNTRY_RAW
    WHERE f.RECORD_TYPE <> 'H'   -- headers are expected in every file; they are not member data
),
checked AS (
    SELECT
        t.*,
        ARRAY_CONSTRUCT_COMPACT(
            IFF(FIELD_COUNT <> 10,                                       'WRONG_FIELD_COUNT', NULL),
            IFF(RECORD_TYPE <> 'D',                                      'UNEXPECTED_RECORD_TYPE', NULL),
            IFF(MEMBER_NAME IS NULL,                                     'MISSING_MEMBER_NAME', NULL),
            IFF(MEMBER_ID IS NULL,                                       'MISSING_MEMBER_ID', NULL),
            IFF(ENROLLMENT_DATE_RAW IS NULL,                             'MISSING_ENROLLMENT_DATE', NULL),
            IFF(ENROLLMENT_DATE_RAW IS NOT NULL AND ENROLLMENT_DATE IS NULL,   'INVALID_ENROLLMENT_DATE', NULL),
            IFF(LAST_FLIGHT_DATE_RAW IS NOT NULL AND LAST_FLIGHT_DATE IS NULL, 'INVALID_LAST_FLIGHT_DATE', NULL),
            IFF(DOB_RAW IS NOT NULL AND DOB IS NULL,                     'INVALID_DOB', NULL),
            IFF(COUNTRY_RAW IS NOT NULL AND COUNTRY IS NULL,             'UNKNOWN_COUNTRY', NULL),
            IFF(COUNTRY_RAW IS NULL,                                     'MISSING_COUNTRY', NULL),
            IFF(LENGTH(MEMBER_NAME) > 255 OR LENGTH(MEMBER_ID) > 18,     'FIELD_TOO_LONG', NULL)
        ) AS DQ_REASONS
    FROM typed t
)
SELECT
    MEMBER_ID,
    MEMBER_NAME,
    ENROLLMENT_DATE,
    LAST_FLIGHT_DATE,
    TIER_CODE,
    AGENT_NAME,
    STATE,
    COUNTRY,
    DOB,
    IS_ACTIVE,
    -- Age: year difference, minus one if this year's birthday hasn't been reached yet.
    DATEDIFF('year', DOB, TO_DATE($RUN_BUSINESS_DATE))
        - IFF(TO_CHAR(TO_DATE($RUN_BUSINESS_DATE), 'MMDD') < TO_CHAR(DOB, 'MMDD'), 1, 0)   AS AGE,
    -- Strictly greater than 90; NULL when there is no flight date (NULL comparisons give NULL).
    DATEDIFF('day', LAST_FLIGHT_DATE, TO_DATE($RUN_BUSINESS_DATE)) > 90                    AS STALE_MEMBER,
    DQ_REASONS,
    IFF(ARRAY_SIZE(DQ_REASONS) = 0, 'VALID', 'REJECTED')                                   AS DQ_STATUS,
    RAW_LINE,
    SOURCE_FILE_NAME,
    SOURCE_LINE_NUMBER,
    FILE_BUSINESS_DATE
FROM checked;