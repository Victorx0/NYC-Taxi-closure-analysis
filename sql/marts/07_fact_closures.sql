-- One row per construction-closure record.
CREATE OR REPLACE TABLE fact_closures AS
SELECT
    location_id,
    borough,
    start_time,
    end_time,
    strftime(start_time, '%Y-%m-%d')                                AS start_date,
    ROUND_EVEN((epoch(end_time) - epoch(start_time)) / 86400, 2)    AS duration_days,
    COALESCE(
        start_time <= getvariable('snapshot_today')
        AND (end_time IS NULL OR end_time >= getvariable('snapshot_today')),
        false
    )                                                               AS active_on_today
FROM stg_closures;
