-- Section 5: active closures per zone at each month-end snapshot. A closure is active on a
-- date if it has started and has not ended (an open-ended closure is still active).

-- Long table. Zones with 0 active closures in a month are kept so Power BI lines don't break.
CREATE OR REPLACE TABLE fact_closure_snapshots AS
WITH active AS (
    SELECT s.snapshot_month, c.location_id, COUNT(*) AS active_closures
    FROM int_snapshot_dates AS s
    JOIN stg_closures AS c
      ON c.start_time <= s.snapshot_date
     AND (c.end_time IS NULL OR c.end_time >= s.snapshot_date)
    GROUP BY ALL
),
zones AS (
    SELECT DISTINCT location_id FROM active
)
SELECT
    z.location_id,
    s.snapshot_month,
    s.snapshot_date,
    COALESCE(a.active_closures, 0) AS active_closures
FROM zones AS z
CROSS JOIN int_snapshot_dates AS s
LEFT JOIN active AS a
       ON a.location_id = z.location_id
      AND a.snapshot_month = s.snapshot_month
ORDER BY s.snapshot_month, z.location_id;

-- Wide table for dim_zone: one active_closures_YYYY_MM column per snapshot.
CREATE OR REPLACE TABLE int_zone_snapshots_wide AS
PIVOT (
    SELECT
        location_id,
        'active_closures_' || replace(snapshot_month, '-', '_') AS snapshot_column,
        active_closures
    FROM fact_closure_snapshots
)
ON snapshot_column
USING first(active_closures)
ORDER BY location_id;

-- Change in active closures between the first and last snapshot.
CREATE OR REPLACE TABLE int_zone_snapshot_change AS
SELECT
    location_id,
    arg_max(active_closures, snapshot_date) - arg_min(active_closures, snapshot_date) AS diff_3mo_total
FROM fact_closure_snapshots
GROUP BY location_id;
