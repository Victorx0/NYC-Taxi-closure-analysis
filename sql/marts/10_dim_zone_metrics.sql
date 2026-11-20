-- One row per taxi zone with every per-zone metric. scripts/export_powerbi.py adds the
-- geometry columns (centroid, area, WKT) and writes it out as dim_zone.csv.
CREATE OR REPLACE TABLE dim_zone_metrics AS
WITH zone_rides AS (
    SELECT
        location_id,
        SUM(ride_count)::BIGINT AS total_rides,
        SUM(revenue)            AS total_real_revenue,
        AVG(avg_trip_duration)  AS avg_trip_duration_sec
    FROM stg_demand
    GROUP BY location_id
),
zone_closures AS (
    SELECT location_id, COUNT(*) AS n_closures
    FROM stg_closures
    GROUP BY location_id
)
SELECT
    l.location_id,
    l.borough,
    l.zone,
    l.service_zone,
    COALESCE(r.total_rides, 0)                    AS total_rides,
    COALESCE(r.total_real_revenue, 0.0)           AS total_real_revenue,
    r.avg_trip_duration_sec,
    r.total_real_revenue / NULLIF(r.total_rides, 0)  AS avg_fare,
    COALESCE(c.n_closures, 0)                     AS n_closures,
    COALESCE(COLUMNS('^active_closures_'), 0),
    COALESCE(sc.diff_3mo_total, 0)                AS diff_3mo_total,
    ri.* EXCLUDE (location_id),
    l.location_id IN (SELECT location_id FROM int_cohort_zones)  AS in_cohort,
    CASE
        WHEN ri.avg_pct_change > 0 THEN 'Increase'
        WHEN ri.avg_pct_change < 0 THEN 'Decrease'
        ELSE 'No data'
    END                                           AS effect_direction
FROM stg_zone_lookup AS l
LEFT JOIN zone_rides               AS r  ON r.location_id = l.location_id
LEFT JOIN zone_closures            AS c  ON c.location_id = l.location_id
LEFT JOIN int_zone_snapshots_wide  AS sw ON sw.location_id = l.location_id
LEFT JOIN int_zone_snapshot_change AS sc ON sc.location_id = l.location_id
LEFT JOIN zone_revenue_impact      AS ri ON ri.location_id = l.location_id
ORDER BY l.location_id;
