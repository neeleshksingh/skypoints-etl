USE SCHEMA SKYPOINTS.STAGING;

-- One row per transaction. A txn_id seen more than once (resent feeds) keeps its first occurrence.
CREATE OR REPLACE TABLE REDEMPTION_STG AS
SELECT
    r.PAYLOAD:member_id::VARCHAR                              AS MEMBER_ID,
    TRY_TO_DATE(r.PAYLOAD:feed_date::VARCHAR, 'YYYYMMDD')     AS FEED_DATE,
    t.value:txn_id::VARCHAR                                   AS TXN_ID,
    TRY_TO_DATE(t.value:txn_date::VARCHAR, 'YYYYMMDD')        AS TXN_DATE,
    t.value:partner::VARCHAR                                  AS PARTNER,
    t.value:miles_redeemed::NUMBER                            AS MILES_REDEEMED,
    t.value:status::VARCHAR                                   AS STATUS,
    t.index                                                   AS TXN_POSITION,
    r.SOURCE_FILE_NAME
FROM SKYPOINTS.RAW.REDEMPTION_FEED_RAW r,
     LATERAL FLATTEN(INPUT => r.PAYLOAD:redemptions) t
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY TXN_ID
    ORDER BY FEED_DATE, SOURCE_FILE_NAME, TXN_POSITION
) = 1;

-- Redemptions joined to the Single Source of Truth for members.
CREATE OR REPLACE VIEW SKYPOINTS.CORE.MEMBER_REDEMPTIONS AS
SELECT
    m.MEMBER_ID, m.MEMBER_NAME, m.COUNTRY, m.TIER_CODE,
    r.TXN_ID, r.TXN_DATE, r.PARTNER, r.MILES_REDEEMED, r.STATUS
FROM SKYPOINTS.STAGING.REDEMPTION_STG r
JOIN SKYPOINTS.CORE.MEMBER_CURRENT m
  ON m.MEMBER_ID = r.MEMBER_ID;