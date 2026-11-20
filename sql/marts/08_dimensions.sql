-- Calendar table covering both the trip data and the closure data, up to snapshot_today.
-- Mark it as the date table in Power BI.
CREATE OR REPLACE TABLE dim_date AS
WITH bounds AS (
    SELECT
        LEAST((SELECT MIN(date) FROM stg_demand),
              (SELECT MIN(start_time)::DATE FROM stg_closures))           AS first_day,
        GREATEST((SELECT MAX(date) FROM stg_demand),
                 getvariable('snapshot_today')::DATE)                     AS last_day
),
days AS (
    SELECT unnest(generate_series(first_day, last_day, INTERVAL 1 DAY))::DATE AS d
    FROM bounds
)
SELECT
    strftime(d, '%Y-%m-%d')  AS date,
    year(d)                  AS year,
    month(d)                 AS month,
    strftime(d, '%b')        AS month_name,
    strftime(d, '%Y-%m')     AS year_month,
    concat('Q', quarter(d))  AS quarter,
    isodow(d)                AS day_of_week,   -- 1 = Monday
    strftime(d, '%a')        AS day_name,
    isodow(d) >= 6           AS is_weekend
FROM days
ORDER BY d;

-- Closure buckets "0", "1", "2", "3+" with a numeric sort order.
CREATE OR REPLACE TABLE dim_closure_bucket AS
SELECT
    CASE
        WHEN bucket_sort = getvariable('max_closure_bucket') THEN bucket_sort::VARCHAR || '+'
        ELSE bucket_sort::VARCHAR
    END AS closure_bucket,
    bucket_sort
FROM (SELECT unnest(range(0, getvariable('max_closure_bucket') + 1)) AS bucket_sort)
ORDER BY bucket_sort;
