-- Like-for-like cohort: zones observed at every required closure level (0, 1 and 2 by default).
-- Comparing only these zones stops changes in WHICH zones appear at each level from
-- looking like a change in demand.
CREATE OR REPLACE TABLE int_cohort_zones AS
WITH zone_bucket_rides AS (
    SELECT location_id, bucket_sort, SUM(ride_count) AS rides
    FROM stg_demand
    GROUP BY ALL
)
SELECT location_id
FROM zone_bucket_rides
WHERE rides >= getvariable('min_location_rides')
  AND (bucket_sort < getvariable('max_closure_bucket') OR getvariable('require_top_bucket'))
GROUP BY location_id
HAVING COUNT(*) = getvariable('max_closure_bucket') + getvariable('require_top_bucket')::INTEGER;

-- Demand rows for cohort zones only.
CREATE OR REPLACE VIEW int_cohort_demand AS
SELECT *
FROM stg_demand
WHERE location_id IN (SELECT location_id FROM int_cohort_zones);
