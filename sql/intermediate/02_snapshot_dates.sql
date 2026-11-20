-- Month-end dates at which active closures are counted (set in scripts/build_warehouse.py).
CREATE OR REPLACE TABLE int_snapshot_dates AS
SELECT
    snapshot_date,
    strftime(snapshot_date, '%Y-%m') AS snapshot_month
FROM (SELECT unnest(getvariable('snapshot_dates')) AS snapshot_date);
