-- TLC taxi zone names and boroughs. 'N/A' and 'NA' (zones 264 and 265) are read as missing.
CREATE OR REPLACE TABLE stg_zone_lookup AS
SELECT
    LocationID::INTEGER  AS location_id,
    Borough              AS borough,
    Zone                 AS zone,
    service_zone
FROM read_csv('data/taxi_zones/taxi+_zone_lookup.csv', nullstr = ['', 'N/A', 'NA']);
