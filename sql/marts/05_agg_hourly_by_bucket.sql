-- Section 4 line chart: cohort demand and revenue by hour of day at each closure level.
CREATE OR REPLACE TABLE agg_hourly_by_bucket AS
SELECT
    hour,
    closure_bucket,
    AVG(ride_count)  AS avg_demand_rides,
    AVG(revenue)     AS avg_revenue,
    SUM(revenue)     AS real_revenue
FROM int_cohort_demand
GROUP BY hour, closure_bucket, bucket_sort
ORDER BY hour, bucket_sort;
