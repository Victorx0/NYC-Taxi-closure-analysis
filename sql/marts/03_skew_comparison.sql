-- Sections 3 and 8: the headline effect of one more concurrent closure, with and without
-- skew management.
--   Skew-managed: cohort zones only; the slope is fitted on the exact counts 1..N-1, so
--                 the pooled "N+" bucket is left out.
--   Unmanaged:    every zone and every exact closure count.
-- regr_slope is an ordinary least-squares fit, the same as np.polyfit(x, y, 1).

-- Unmanaged demand at every exact closure count (section 8 curve).
CREATE OR REPLACE TABLE agg_demand_by_closure_count AS
SELECT
    construction_count,
    AVG(ride_count)              AS avg_demand,
    COUNT(*)                     AS n_obs,
    COUNT(DISTINCT location_id)  AS n_zones
FROM stg_demand
GROUP BY construction_count
ORDER BY construction_count;

CREATE OR REPLACE TABLE skew_comparison AS
WITH managed_by_bucket AS (
    SELECT bucket_sort AS closure_count, AVG(ride_count) AS avg_demand
    FROM int_cohort_demand
    GROUP BY bucket_sort
),
managed AS (
    SELECT
        'Skew-managed (current)'                                     AS method,
        (SELECT COUNT(*) FROM int_cohort_zones)                      AS zones,
        MIN(closure_count) FILTER (WHERE closure_count >= 1)         AS closure_count_min,
        MAX(closure_count) FILTER (WHERE closure_count >= 1)         AS closure_count_max,
        MAX(avg_demand) FILTER (WHERE closure_count = 0)             AS baseline_rides_per_loc_hr,
        regr_slope(avg_demand, closure_count) FILTER (WHERE closure_count >= 1)
                                                                     AS change_per_closure_rides
    FROM managed_by_bucket
    WHERE closure_count < getvariable('max_closure_bucket')          -- drop the pooled "N+" bucket
),
unmanaged AS (
    SELECT
        'No skew management'                                         AS method,
        (SELECT COUNT(DISTINCT location_id) FROM stg_demand)         AS zones,
        MIN(construction_count) FILTER (WHERE construction_count >= 1),
        MAX(construction_count) FILTER (WHERE construction_count >= 1),
        MAX(avg_demand) FILTER (WHERE construction_count = 0),
        regr_slope(avg_demand, construction_count) FILTER (WHERE construction_count >= 1)
    FROM agg_demand_by_closure_count
)
SELECT *, change_per_closure_rides / baseline_rides_per_loc_hr * 100 AS change_per_closure_pct
FROM (
    SELECT * FROM managed
    UNION ALL
    SELECT * FROM unmanaged
);
