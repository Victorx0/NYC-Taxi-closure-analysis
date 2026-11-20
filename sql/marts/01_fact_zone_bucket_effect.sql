-- Section 6: each cohort zone's demand and revenue at each closure level, measured against
-- that zone's own 0-closure baseline. Expected revenue = the same hours at the zone's
-- 0-closure revenue rate.
CREATE OR REPLACE TABLE fact_zone_bucket_effect AS
WITH per_zone AS (
    SELECT
        location_id,
        closure_bucket,
        bucket_sort,
        AVG(ride_count)          AS avg_demand,
        COUNT(*)                 AS n_obs,
        SUM(ride_count)::BIGINT  AS total_rides,  -- SUM of BIGINT is HUGEINT; keep it a plain integer
        SUM(revenue)             AS real_revenue,
        SUM(revenue) / COUNT(*)  AS avg_revenue
    FROM int_cohort_demand
    GROUP BY ALL
),
with_baseline AS (
    SELECT
        *,
        MAX(avg_demand)  FILTER (WHERE bucket_sort = 0) OVER zone  AS baseline_demand,
        MAX(avg_revenue) FILTER (WHERE bucket_sort = 0) OVER zone  AS baseline_revenue
    FROM per_zone
    WINDOW zone AS (PARTITION BY location_id)
),
with_expected AS (
    SELECT *, baseline_revenue * n_obs AS expected_revenue
    FROM with_baseline
    WHERE baseline_demand IS NOT NULL
)
SELECT
    location_id,
    closure_bucket,
    avg_demand,
    n_obs,
    total_rides,
    real_revenue,
    avg_revenue,
    baseline_demand,
    baseline_revenue,
    avg_demand - baseline_demand                                        AS demand_change_amount,
    (avg_demand - baseline_demand) / NULLIF(baseline_demand, 0) * 100   AS demand_change_pct,
    real_revenue / NULLIF(total_rides, 0)                               AS avg_fare,
    expected_revenue,
    real_revenue - expected_revenue                                     AS revenue_vs_expected,
    (real_revenue - expected_revenue) / NULLIF(expected_revenue, 0) * 100
                                                                        AS revenue_vs_expected_pct
FROM with_expected
ORDER BY location_id, bucket_sort;
