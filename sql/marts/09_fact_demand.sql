-- Full-grain demand fact: date x hour x zone x service, with the cohort flag.
-- A view, so the warehouse doesn't store a second copy of stg_demand.
CREATE OR REPLACE VIEW fact_demand AS
SELECT
    date,
    hour,
    location_id,
    taxi_type,
    ride_count,
    avg_total_amount,
    avg_trip_duration,
    construction_count,
    closure_bucket,
    revenue,
    location_id IN (SELECT location_id FROM int_cohort_zones) AS in_cohort
FROM stg_demand;
