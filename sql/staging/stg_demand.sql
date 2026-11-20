-- Pickup demand at the grain date x hour x pickup zone x service, from taxi_preprocess.ipynb.
-- Adds the closure bucket ("0", "1", "2", "3+") and observed revenue.
CREATE OR REPLACE TABLE stg_demand AS
SELECT
    date,
    hour,
    location_id,
    taxi_type,
    ride_count,
    avg_total_amount,
    avg_trip_duration,
    construction_count,
    CASE
        WHEN construction_count >= getvariable('max_closure_bucket')
            THEN getvariable('max_closure_bucket')::VARCHAR || '+'
        ELSE construction_count::VARCHAR
    END                                                              AS closure_bucket,
    LEAST(construction_count, getvariable('max_closure_bucket'))     AS bucket_sort,
    -- Real revenue = rides x avg fare. Fare is only missing on 0-ride rows, so those earn $0.
    COALESCE(ride_count * avg_total_amount, 0.0)                     AS revenue
FROM read_parquet('data/processed/pu_agg.parquet')
WHERE location_id IS NOT NULL;
