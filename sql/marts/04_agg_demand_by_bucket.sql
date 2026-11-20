-- Section 3 bar chart: cohort demand and revenue at 0..19 concurrent closures, plus "20+".
-- Expected revenue for each row = that zone's own 0-closure revenue rate, so the comparison
-- isn't distorted by which zones happen to fall in each bucket.
CREATE OR REPLACE TABLE agg_demand_by_bucket AS
WITH zone_baseline AS (
    SELECT location_id, baseline_revenue
    FROM fact_zone_bucket_effect
    WHERE closure_bucket = '0'
),
by_bucket AS (
    SELECT
        LEAST(d.construction_count, getvariable('agg_max_bucket'))  AS bucket_sort,
        AVG(d.ride_count)                                           AS avg_demand,
        COUNT(*)                                                    AS n_obs,
        SUM(d.ride_count)::BIGINT                                   AS total_rides,
        COUNT(DISTINCT d.location_id)                               AS n_zones,
        SUM(d.revenue)                                              AS real_revenue,
        SUM(b.baseline_revenue)                                     AS expected_revenue
    FROM int_cohort_demand AS d
    LEFT JOIN zone_baseline AS b USING (location_id)
    GROUP BY 1
),
baseline AS (
    SELECT baseline_rides_per_loc_hr AS baseline_demand
    FROM skew_comparison
    WHERE method = 'Skew-managed (current)'
)
SELECT
    CASE
        WHEN bucket_sort < getvariable('agg_max_bucket') THEN bucket_sort::VARCHAR
        ELSE getvariable('agg_max_bucket')::VARCHAR || '+'
    END                                                     AS closure_bucket,
    bucket_sort,
    avg_demand,
    n_obs,
    total_rides,
    n_zones,
    (avg_demand - baseline_demand) / baseline_demand * 100  AS pct_change_vs_no_closure,
    real_revenue / total_rides                              AS avg_fare,
    real_revenue / n_obs                                    AS avg_revenue,
    real_revenue,
    expected_revenue,
    real_revenue - expected_revenue                         AS revenue_vs_expected,
    (real_revenue - expected_revenue) / expected_revenue * 100
                                                            AS revenue_vs_expected_pct
FROM by_bucket, baseline
ORDER BY bucket_sort;
