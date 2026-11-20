-- Headline numbers for the report, one row per metric. Values are text because the table
-- mixes counts, money and dates.
CREATE OR REPLACE TABLE kpi_summary AS
WITH managed AS (
    SELECT * FROM skew_comparison WHERE method = 'Skew-managed (current)'
),
trip_period AS (
    SELECT MIN(date) AS trip_start, MAX(date) AS trip_end FROM stg_demand
),
metric_values AS (
    SELECT
        (SELECT zones FROM managed)                                       AS cohort_zones,
        (SELECT baseline_rides_per_loc_hr FROM managed)                   AS baseline_demand,
        (SELECT change_per_closure_rides FROM managed)                    AS marginal_change_per_closure,
        (SELECT change_per_closure_pct FROM managed)                      AS marginal_change_per_closure_pct,
        (SELECT SUM(total_incremental_rides) FROM zone_revenue_impact)    AS total_incremental_rides,
        (SELECT SUM(total_revenue_gain) FROM zone_revenue_impact)         AS total_revenue_gain,
        (SELECT SUM(revenue) FROM stg_demand)                             AS total_real_revenue,
        (SELECT SUM(real_revenue_with_closures) FROM zone_revenue_impact) AS cohort_real_revenue_with_closures,
        (SELECT SUM(expected_revenue_with_closures) FROM zone_revenue_impact)
                                                                          AS cohort_expected_revenue_with_closures,
        (SELECT SUM(revenue_vs_expected) FROM zone_revenue_impact)        AS cohort_revenue_vs_expected,
        strftime(getvariable('snapshot_today'), '%Y-%m-%d')               AS snapshot_today,
        (SELECT COUNT(*) FROM stg_closures)                               AS total_closures,
        (SELECT COUNT(*) FROM (SELECT DISTINCT location_id, start_time, end_time FROM stg_closures))
                                                                          AS distinct_closures,
        (SELECT COUNT_IF(c.start_time < t.trip_end + INTERVAL 1 DAY
                         AND (c.end_time IS NULL OR c.end_time >= t.trip_start))
           FROM stg_closures AS c, trip_period AS t)                      AS closures_in_trip_period,
        (SELECT COUNT(*) FILTER (WHERE active_on_today) FROM fact_closures)
                                                                          AS closures_active_today,
        (SELECT COUNT(DISTINCT location_id) FROM stg_closures)            AS zones_with_closures,
        (SELECT strftime(trip_start, '%Y-%m-%d') FROM trip_period)        AS trip_data_start,
        (SELECT strftime(trip_end, '%Y-%m-%d') FROM trip_period)          AS trip_data_end,
        (SELECT date_diff('month', trip_start, trip_end) + 1 FROM trip_period)
                                                                          AS trip_data_months,
        (SELECT strftime(MIN(start_time), '%Y-%m-%d') FROM stg_closures)  AS closure_data_start,
        (SELECT strftime(MAX(start_time), '%Y-%m-%d') FROM stg_closures)  AS closure_data_end
),
metric_long AS (
    UNPIVOT (SELECT COLUMNS(*)::VARCHAR FROM metric_values)
    ON COLUMNS(*)
    INTO NAME metric VALUE value
)
SELECT m.metric, v.value, m.unit, m.description
FROM (VALUES
    (1,  'cohort_zones',                          'zones',             'Zones observed at 0, 1 and 2 concurrent closures'),
    (2,  'baseline_demand',                       'rides/location-hr', 'Avg demand with 0 closures (cohort)'),
    (3,  'marginal_change_per_closure',           'rides/location-hr', 'Slope over 1..N-1 closures'),
    (4,  'marginal_change_per_closure_pct',       '%',                 'Slope as % of baseline'),
    (5,  'total_incremental_rides',               'rides',             'Positive-shift zones'),
    (6,  'total_revenue_gain',                    'USD',               'Estimated gross revenue gain'),
    (7,  'total_real_revenue',                    'USD',               'Observed revenue, all zones and hours'),
    (8,  'cohort_real_revenue_with_closures',     'USD',               'Observed revenue in cohort zone-hours with >=1 closure'),
    (9,  'cohort_expected_revenue_with_closures', 'USD',               'Same zone-hours at each zone''s 0-closure revenue rate'),
    (10, 'cohort_revenue_vs_expected',            'USD',               'Real minus expected revenue during closures'),
    (11, 'snapshot_today',                        'date',              'Reference date for active closures'),
    (12, 'total_closures',                        'closures',          'Closure records (one per street segment / OFT code)'),
    (13, 'distinct_closures',                     'closures',          'Unique zone + start + end combinations (one per project per zone)'),
    (14, 'closures_in_trip_period',               'closures',          'Closure records overlapping the trip data period'),
    (15, 'closures_active_today',                 'closures',          'Closure records active on snapshot_today'),
    (16, 'zones_with_closures',                   'zones',             'Taxi zones with at least one closure'),
    (17, 'trip_data_start',                       'date',              'First date in trip data'),
    (18, 'trip_data_end',                         'date',              'Last date in trip data'),
    (19, 'trip_data_months',                      'months',            'Calendar months covered by trip data'),
    (20, 'closure_data_start',                    'date',              'Earliest closure start'),
    (21, 'closure_data_end',                      'date',              'Latest closure start')
) AS m(sort_order, metric, unit, description)
LEFT JOIN metric_long AS v USING (metric)
ORDER BY m.sort_order;
