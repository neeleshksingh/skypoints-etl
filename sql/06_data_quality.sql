USE SCHEMA SKYPOINTS.CORE;

SET RUN_BUSINESS_DATE = '2024-01-15';

-- One row per problem found. ERROR = record held back; WARNING = loaded but needs review.
CREATE OR REPLACE TABLE DQ_ISSUES AS

-- 1. Every reason a staging record was rejected (one row per reason)
SELECT 'REJECTED_RECORD' AS CHECK_NAME, 'ERROR' AS SEVERITY,
       s.MEMBER_ID AS ENTITY_KEY,
       r.value::VARCHAR || ' (' || s.SOURCE_FILE_NAME || ' line ' || s.SOURCE_LINE_NUMBER::VARCHAR || ')' AS DETAIL
FROM SKYPOINTS.STAGING.MEMBER_PROFILE_STG s,
     LATERAL FLATTEN(INPUT => s.DQ_REASONS) r
WHERE s.DQ_STATUS = 'REJECTED'

UNION ALL
-- 2. Key uniqueness: the SSOT must hold exactly one row per member
SELECT 'DUPLICATE_MEMBER_ID', 'ERROR', MEMBER_ID, COUNT(*)::VARCHAR || ' rows'
FROM MEMBER_CURRENT
GROUP BY MEMBER_ID HAVING COUNT(*) > 1

UNION ALL
-- 3. Key uniqueness: each transaction counted once (guards the dedupe in staging)
SELECT 'DUPLICATE_TXN_ID', 'ERROR', TXN_ID, COUNT(*)::VARCHAR || ' rows'
FROM SKYPOINTS.STAGING.REDEMPTION_STG
GROUP BY TXN_ID HAVING COUNT(*) > 1

UNION ALL
-- 3a. Resent transactions: the same txn_id received more than once (staging keeps the first copy)
SELECT 'RESENT_TXN_ID', 'WARNING', t.value:txn_id::VARCHAR, COUNT(*)::VARCHAR || ' copies received'
FROM SKYPOINTS.RAW.REDEMPTION_FEED_RAW r,
     LATERAL FLATTEN(INPUT => r.PAYLOAD:redemptions) t
GROUP BY t.value:txn_id::VARCHAR
HAVING COUNT(*) > 1

UNION ALL
-- 3b. Redemption fields that can't be trusted, checked on the raw feed so nothing is collapsed by dedupe
SELECT 'INVALID_REDEMPTION', 'ERROR', ENTITY_KEY, ARRAY_TO_STRING(PROBLEMS, ', ')
FROM (
    SELECT
        COALESCE(t.value:txn_id::VARCHAR,
                 r.PAYLOAD:member_id::VARCHAR || ' item ' || t.index::VARCHAR)          AS ENTITY_KEY,
        ARRAY_CONSTRUCT_COMPACT(
            IFF(t.value:txn_id::VARCHAR IS NULL, 'MISSING_TXN_ID', NULL),
            IFF(TRY_TO_DATE(t.value:txn_date::VARCHAR, 'YYYYMMDD') IS NULL, 'INVALID_TXN_DATE', NULL),
            IFF(COALESCE(TRY_TO_NUMBER(t.value:miles_redeemed::VARCHAR), 0) <= 0, 'MILES_NOT_POSITIVE', NULL),
            IFF(t.value:status::VARCHAR IS NULL, 'MISSING_STATUS', NULL)
        )                                                                             AS PROBLEMS
    FROM SKYPOINTS.RAW.REDEMPTION_FEED_RAW r,
         LATERAL FLATTEN(INPUT => r.PAYLOAD:redemptions) t
)
WHERE ARRAY_SIZE(PROBLEMS) > 0

UNION ALL
-- 4. Redemptions for members we don't have
SELECT 'ORPHAN_REDEMPTION', 'WARNING', r.TXN_ID, 'member_id ' || r.MEMBER_ID || ' not in MEMBER_CURRENT'
FROM SKYPOINTS.STAGING.REDEMPTION_STG r
LEFT JOIN MEMBER_CURRENT m ON m.MEMBER_ID = r.MEMBER_ID
WHERE m.MEMBER_ID IS NULL

UNION ALL
-- 5. Valid per spec, but possibly truncated upstream
SELECT 'SHORT_MEMBER_ID', 'WARNING', MEMBER_ID, 'length ' || LENGTH(MEMBER_ID)::VARCHAR
FROM MEMBER_CURRENT
WHERE LENGTH(MEMBER_ID) < 6

UNION ALL
-- 6. Logically impossible dates on records that passed format checks
SELECT 'FLIGHT_BEFORE_ENROLLMENT', 'WARNING', MEMBER_ID, LAST_FLIGHT_DATE::VARCHAR || ' < ' || ENROLLMENT_DATE::VARCHAR
FROM MEMBER_CURRENT
WHERE LAST_FLIGHT_DATE < ENROLLMENT_DATE

UNION ALL
SELECT 'DATE_AFTER_BUSINESS_DATE', 'WARNING', MEMBER_ID, 'DOB, enrollment or flight after ' || $RUN_BUSINESS_DATE
FROM MEMBER_CURRENT
WHERE DOB > TO_DATE($RUN_BUSINESS_DATE)
   OR ENROLLMENT_DATE > TO_DATE($RUN_BUSINESS_DATE)
   OR LAST_FLIGHT_DATE > TO_DATE($RUN_BUSINESS_DATE)

UNION ALL
-- 7. Business clarification needed: the programme itself listed as a partner
SELECT 'PARTNER_IS_PROGRAMME', 'WARNING', TXN_ID, 'partner = ' || PARTNER
FROM SKYPOINTS.STAGING.REDEMPTION_STG
WHERE PARTNER = 'SkyPoints'

UNION ALL
-- 8. Reconciliation: every non-header raw line must reach staging
SELECT 'RAW_TO_STAGING_RECONCILE', 'ERROR', NULL,
       'raw ' || raw_count::VARCHAR || ' vs staging ' || stg_count::VARCHAR
FROM (
    SELECT
        (SELECT COUNT(*) FROM SKYPOINTS.RAW.MEMBER_PROFILE_RAW WHERE SPLIT_PART(RAW_LINE, '|', 2) IS DISTINCT FROM 'H') AS raw_count,
        (SELECT COUNT(*) FROM SKYPOINTS.STAGING.MEMBER_PROFILE_STG)                                                   AS stg_count
)
WHERE raw_count <> stg_count

UNION ALL
-- 9. Reconciliation: country tables together must equal the SSOT
SELECT 'COUNTRY_TABLES_RECONCILE', 'ERROR', NULL,
       'country tables ' || country_total::VARCHAR || ' vs MEMBER_CURRENT ' || current_total::VARCHAR
FROM (
    SELECT
        (SELECT COALESCE(SUM(ROW_COUNT), 0)
           FROM SKYPOINTS.INFORMATION_SCHEMA.TABLES
          WHERE TABLE_SCHEMA = 'CORE' AND TABLE_TYPE = 'BASE TABLE'
            AND TABLE_NAME LIKE 'MEMBERS!_%' ESCAPE '!')      AS country_total,
        (SELECT COUNT(*) FROM MEMBER_CURRENT)                 AS current_total
)
WHERE country_total <> current_total;