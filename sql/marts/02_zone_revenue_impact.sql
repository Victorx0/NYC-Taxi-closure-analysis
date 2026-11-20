-- Sections 6-7: one row per cohort zone. Averages the zone's demand change across all
-- closure levels, then estimates revenue gained from any positive shift in demand.
CREATE OR REPLACE TABLE zone_revenue_impact AS
WITH overall AS (
    SELECT
        location_id,
        AVG(demand_change_amount)  AS avg_amount_change,
        AVG(demand_change_pct)     AS avg_pct_change,
        SUM(real_revenue)          AS real_revenue_with_closures,
        SUM(expected_revenue)      AS expected_revenue_with_closures,
        SUM(revenue_vs_expected)   AS revenue_vs_expected
    FROM fact_zone_bucket_effect
    WHERE closure_bucket <> '0'
    GROUP BY location_id
),
zone_fares AS (
    SELECT
        location_id,
        AVG(avg_total_amount)  AS mean_zone_fare,
        COUNT(DISTINCT hour)   AS observed_hours
    FROM int_cohort_demand
    GROUP BY location_id
),
shift AS (
    SELECT
        o.*,
        o.revenue_vs_expected / NULLIF(o.expected_revenue_with_closures, 0) * 100  AS revenue_vs_expected_pct,
        f.mean_zone_fare,
        f.observed_hours,
        CASE WHEN o.avg_amount_change < 0 THEN 0 ELSE o.avg_amount_change END    AS positive_hourly_shift
    FROM overall AS o
    JOIN zone_fares AS f USING (location_id)
)
SELECT
    *,
    positive_hourly_shift * observed_hours                   AS total_incremental_rides,
    positive_hourly_shift * observed_hours * mean_zone_fare  AS total_revenue_gain
FROM shift
ORDER BY location_id;
