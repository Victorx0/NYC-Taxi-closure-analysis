"""Export the analysis as Power BI-ready tables (star schema, tidy/long format, one shared
key: location_id).

The numbers come from the SQL in sql/, which this script first builds into
data/warehouse.duckdb (see scripts/build_warehouse.py). This script then adds the zone
geometry with GeoPandas and writes every table to data/powerbi/.

Run from anywhere:   python scripts/export_powerbi.py
Output:              data/powerbi/

Dimensions
  dim_zone.csv                 one row per taxi zone: names, borough, centroid lat/lon, WKT,
                               plus every per-zone metric from the analysis (maps 1, 2, 5, 6, 7)
  dim_date.csv                 calendar table (mark as date table in Power BI)
  dim_closure_bucket.csv       "0", "1", "2", "3+" with a numeric sort order
  taxi_zones.geojson           WGS84 polygons (Azure Maps / Icon Map / Deneb; convert to
                               TopoJSON with mapshaper.org for the built-in Shape Map)
Facts
  fact_demand.parquet          full grain: date x hour x zone x taxi_type (+ bucket, cohort flag)
  fact_closures.csv            one row per construction-closure event
  fact_closure_snapshots.csv   active closures per zone at month-end snapshots (section 5)
  fact_zone_bucket_effect.csv  per-zone demand vs. own 0-closure baseline, per bucket (section 6)
Summary tables (pre-computed visuals)
  agg_demand_by_bucket.csv     section 3 bar chart
  agg_hourly_by_bucket.csv     section 4 line chart
  agg_demand_by_closure_count.csv  section 8 unmanaged curve
  kpi_summary.csv              headline numbers (baseline, slope, revenue gain, ...)
  skew_comparison.csv          section 8 managed vs unmanaged
"""

import geopandas as gpd
import pandas as pd

from build_warehouse import ROOT, build

DATA = ROOT / "data"
OUT = DATA / "powerbi"

# Warehouse tables written as-is, one CSV each.
CSV_TABLES = [
    "dim_date", "dim_closure_bucket",
    "fact_closures", "fact_closure_snapshots", "fact_zone_bucket_effect",
    "agg_demand_by_bucket", "agg_hourly_by_bucket", "agg_demand_by_closure_count",
    "skew_comparison", "kpi_summary",
]


def save_csv(df, name):
    df.to_csv(OUT / name, index=False, date_format="%Y-%m-%d %H:%M:%S")
    print(f"  {name:<34} {len(df):>10,} rows")


def zone_geometry():
    """Centroid, area and simplified outline for each zone, plus the GeoJSON for map visuals."""
    zones = gpd.read_file(DATA / "taxi_zones" / "taxi_zones.shp")
    zones_wgs = zones.to_crs(epsg=4326)
    centroids = zones.geometry.centroid.to_crs(epsg=4326)  # centroid in projected CRS, then reproject
    geo = pd.DataFrame({
        "location_id": zones["LocationID"].astype(int),
        "latitude": centroids.y.round(6),
        "longitude": centroids.x.round(6),
        "area_sq_km": (zones.geometry.area * 0.09290304 / 1e6).round(4),  # EPSG:2263 is US feet
        "wkt": zones_wgs.geometry.simplify(0.0002, preserve_topology=True).to_wkt(),
    }).drop_duplicates("location_id")
    geojson = zones_wgs[["LocationID", "zone", "borough", "geometry"]].assign(
        geometry=zones_wgs.geometry.simplify(0.0001, preserve_topology=True)
    ).rename(columns={"LocationID": "location_id"})
    return geo, geojson


def main():
    con = build()
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"Writing to {OUT}")

    # --- dim_zone: warehouse metrics + geometry, geometry columns right after the names ---
    geo, geojson = zone_geometry()
    metrics = con.table("dim_zone_metrics").df()
    name_cols = ["location_id", "borough", "zone", "service_zone"]
    dim_zone = metrics.merge(geo, on="location_id", how="left")
    dim_zone = dim_zone[name_cols + list(geo.columns[1:]) + [c for c in metrics if c not in name_cols]]
    save_csv(dim_zone, "dim_zone.csv")

    geojson.to_file(OUT / "taxi_zones.geojson", driver="GeoJSON")
    print(f"  {'taxi_zones.geojson':<34} {len(geojson):>10,} shapes")

    # --- every other table comes straight from the warehouse ---
    for name in CSV_TABLES:
        save_csv(con.table(name).df(), f"{name}.csv")

    con.execute(f"COPY fact_demand TO '{(OUT / 'fact_demand.parquet').as_posix()}' (FORMAT parquet)")
    rows = con.execute("SELECT COUNT(*) FROM fact_demand").fetchall()[0][0]
    print(f"  {'fact_demand.parquet':<34} {rows:>10,} rows")

    kpi = con.table("kpi_summary").df().set_index("metric")["value"].astype(object)
    print("\nCheck against analysis.ipynb:")
    print(f"  baseline {float(kpi['baseline_demand']):.3f}  "
          f"slope {float(kpi['marginal_change_per_closure']):+.3f}  "
          f"pct {float(kpi['marginal_change_per_closure_pct']):+.2f}%  "
          f"revenue ${float(kpi['total_revenue_gain']):,.2f}")
    con.close()


if __name__ == "__main__":
    main()
