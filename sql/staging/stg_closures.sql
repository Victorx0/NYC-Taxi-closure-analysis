-- One row per construction closure, mapped to a taxi zone by construction_closures.ipynb.
-- Unparseable timestamps become NULL; closures with no zone are dropped.
CREATE OR REPLACE TABLE stg_closures AS
SELECT
    TRY_CAST(location_id AS DOUBLE)::INTEGER  AS location_id,
    borough,
    TRY_CAST(start_time AS TIMESTAMP)         AS start_time,
    TRY_CAST(end_time AS TIMESTAMP)           AS end_time
FROM read_csv('data/processed/construction_closures.csv', all_varchar = true)
WHERE TRY_CAST(location_id AS DOUBLE) IS NOT NULL;
