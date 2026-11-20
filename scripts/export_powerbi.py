"""Export the results of `notebooks/Geospatial Visualisation/analysis.ipynb` as
Power BI-ready tables (star schema, tidy/long format, one shared key: location_id).

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

from datetime import datetime
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

# --------------------------------------------- parameters (match analysis.ipynb) ----
MIN_LOCATION_RIDES = 0
MAX_CLOSURE_BUCKET = 3
AGG_MAX_BUCKET = 20   # finer bucketing for agg_demand_by_bucket.csv only: 0..9, "10+"
REQUIRE_TOP_BUCKET = False
TODAY = datetime(2026, 8, 31)
SNAPSHOTS = {
    "2026-05": datetime(2026, 5, 31),
    "2026-06": datetime(2026, 6, 30),
    "2026-07": datetime(2026, 7, 31),
    "2026-08": TODAY,
}

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "powerbi"
OUT.mkdir(parents=True, exist_ok=True)

BUCKET_ORDER = [str(i) for i in range(MAX_CLOSURE_BUCKET)] + [f"{MAX_CLOSURE_BUCKET}+"]


def save_csv(df, name):
    df.to_csv(OUT / name, index=False, date_format="%Y-%m-%d %H:%M:%S")
    print(f"  {name:<34} {len(df):>10,} rows")


def to_bucket(counts):
    return np.where(counts >= MAX_CLOSURE_BUCKET, f"{MAX_CLOSURE_BUCKET}+", counts.astype(str))


# ----------------------------------------------------------------------- load ----
print("Loading inputs ...")
pu = pd.read_parquet(DATA / "processed" / "pu_agg.parquet")
pu["date"] = pd.to_datetime(pu["date"])
pu["taxi_type"] = pu["taxi_type"].astype("category")
pu = pu.dropna(subset=["location_id"])
pu["location_id"] = pu["location_id"].astype("int32")
pu["closure_bucket"] = pd.Categorical(to_bucket(pu["construction_count"].to_numpy()), BUCKET_ORDER, ordered=True)
# Real revenue = rides x avg fare. Fare is only missing on 0-ride rows, so those earn $0.
pu["revenue"] = (pu["ride_count"] * pu["avg_total_amount"]).fillna(0.0)

closures = pd.read_csv(DATA / "processed" / "construction_closures.csv")
closures["start_time"] = pd.to_datetime(closures["start_time"], errors="coerce")
closures["end_time"] = pd.to_datetime(closures["end_time"], errors="coerce")
closures = closures.dropna(subset=["location_id"])
closures["location_id"] = closures["location_id"].astype("int32")

zones = gpd.read_file(DATA / "taxi_zones" / "taxi_zones.shp")
lookup = pd.read_csv(DATA / "taxi_zones" / "taxi+_zone_lookup.csv")

# ------------------------------------------------- cohort (common locations) ----
required = BUCKET_ORDER[:-1] + ([BUCKET_ORDER[-1]] if REQUIRE_TOP_BUCKET else [])
loc_bucket_rides = pu.groupby(["location_id", "closure_bucket"], observed=True)["ride_count"].sum().reset_index()
loc_bucket_rides = loc_bucket_rides[
    (loc_bucket_rides["ride_count"] >= MIN_LOCATION_RIDES) & loc_bucket_rides["closure_bucket"].isin(required)
]
n_buckets = loc_bucket_rides.groupby("location_id")["closure_bucket"].nunique()
common_locations = set(n_buckets[n_buckets == len(required)].index)
pu["in_cohort"] = pu["location_id"].isin(common_locations)
bucketed = pu[pu["in_cohort"]]
print(f"Locations in closure-bucket cohort: {len(common_locations)}")

# --------------------------------------------- section 3: demand by bucket ----
by_bucket = bucketed.groupby("closure_bucket", observed=True).agg(
    avg_demand=("ride_count", "mean"), n_obs=("ride_count", "size"), total_rides=("ride_count", "sum")
).reset_index()
baseline = by_bucket.loc[by_bucket["closure_bucket"] == "0", "avg_demand"].iloc[0]
by_bucket["pct_change_vs_no_closure"] = (by_bucket["avg_demand"] - baseline) / baseline * 100

marginal = by_bucket[by_bucket["closure_bucket"].astype(str).str.isnumeric()].copy()
marginal["closure_count"] = marginal["closure_bucket"].astype(str).astype(int)
marginal = marginal[marginal["closure_count"] >= 1]
slope = np.polyfit(marginal["closure_count"], marginal["avg_demand"], 1)[0] if len(marginal) >= 2 else np.nan

# --------------------------------------------- section 4: hourly by bucket ----
hourly = bucketed.groupby(["hour", "closure_bucket"], observed=True).agg(
    avg_demand_rides=("ride_count", "mean"), avg_revenue=("revenue", "mean"), real_revenue=("revenue", "sum"),
).reset_index()

# -------------------------------------------- section 5: closure snapshots ----
snap_rows = []
for label, dt in SNAPSHOTS.items():
    active = closures[(closures["start_time"] <= dt) & (closures["end_time"].isna() | (closures["end_time"] >= dt))]
    counts = active.groupby("location_id").size().rename("active_closures").reset_index()
    counts["snapshot_month"], counts["snapshot_date"] = label, dt
    snap_rows.append(counts)
snapshots = pd.concat(snap_rows, ignore_index=True)
snap_wide = (
    snapshots.pivot(index="location_id", columns="snapshot_month", values="active_closures").fillna(0).astype(int)
)
first, last = list(SNAPSHOTS)[0], list(SNAPSHOTS)[-1]
snap_wide["diff_3mo_total"] = snap_wide[last] - snap_wide[first]
snap_wide = snap_wide.rename(columns={m: f"active_closures_{m.replace('-', '_')}" for m in SNAPSHOTS}).reset_index()
# Long table: fill zones with 0 active closures so Power BI lines don't break.
snapshots = (
    snap_wide.melt(id_vars="location_id", value_vars=[c for c in snap_wide if c.startswith("active_")],
                   var_name="snapshot_month", value_name="active_closures")
)
snapshots["snapshot_month"] = snapshots["snapshot_month"].str.replace("active_closures_", "").str.replace("_", "-")
snapshots["snapshot_date"] = snapshots["snapshot_month"].map(SNAPSHOTS)

# ------------------------------------------ section 6: per-zone effect ----
per_loc = bucketed.groupby(["location_id", "closure_bucket"], observed=True).agg(
    avg_demand=("ride_count", "mean"), n_obs=("ride_count", "size"),
    total_rides=("ride_count", "sum"), real_revenue=("revenue", "sum"),
).reset_index()
per_loc["avg_revenue"] = per_loc["real_revenue"] / per_loc["n_obs"]
per_loc_base = per_loc.loc[per_loc["closure_bucket"] == "0", ["location_id", "avg_demand", "avg_revenue"]].rename(
    columns={"avg_demand": "baseline_demand", "avg_revenue": "baseline_revenue"}
)
region_change = per_loc.merge(per_loc_base, on="location_id")
region_change["demand_change_amount"] = region_change["avg_demand"] - region_change["baseline_demand"]
region_change["demand_change_pct"] = np.where(
    region_change["baseline_demand"] == 0, np.nan,
    region_change["demand_change_amount"] / region_change["baseline_demand"] * 100,
)
# Revenue: real (observed) vs expected (same hours at the zone's own 0-closure revenue rate).
region_change["avg_fare"] = region_change["real_revenue"] / region_change["total_rides"].replace(0, np.nan)
region_change["expected_revenue"] = region_change["baseline_revenue"] * region_change["n_obs"]
region_change["revenue_vs_expected"] = region_change["real_revenue"] - region_change["expected_revenue"]
region_change["revenue_vs_expected_pct"] = np.where(
    region_change["expected_revenue"] == 0, np.nan,
    region_change["revenue_vs_expected"] / region_change["expected_revenue"] * 100,
)
overall_effect = (
    region_change[region_change["closure_bucket"] != "0"]
    .groupby("location_id")
    .agg(avg_amount_change=("demand_change_amount", "mean"), avg_pct_change=("demand_change_pct", "mean"),
         real_revenue_with_closures=("real_revenue", "sum"),
         expected_revenue_with_closures=("expected_revenue", "sum"),
         revenue_vs_expected=("revenue_vs_expected", "sum"))
    .reset_index()
)
overall_effect["revenue_vs_expected_pct"] = (
    overall_effect["revenue_vs_expected"] / overall_effect["expected_revenue_with_closures"].replace(0, np.nan) * 100
)

# ----------------------------------------------- section 7: revenue impact ----
zone_revenue = bucketed.groupby("location_id").agg(
    mean_zone_fare=("avg_total_amount", "mean"), observed_hours=("hour", "nunique")
).reset_index()
revenue = overall_effect.merge(zone_revenue, on="location_id")
revenue["positive_hourly_shift"] = revenue["avg_amount_change"].clip(lower=0)
revenue["total_incremental_rides"] = revenue["positive_hourly_shift"] * revenue["observed_hours"]
revenue["total_revenue_gain"] = revenue["total_incremental_rides"] * revenue["mean_zone_fare"]

# -------------------------------------------- section 8: skew comparison ----
raw_by_count = pu.groupby("construction_count").agg(
    avg_demand=("ride_count", "mean"), n_obs=("ride_count", "size"), n_zones=("location_id", "nunique")
).reset_index()
raw_baseline = raw_by_count.loc[raw_by_count["construction_count"] == 0, "avg_demand"].iloc[0]
raw_marginal = raw_by_count[raw_by_count["construction_count"] >= 1]
raw_slope = np.polyfit(raw_marginal["construction_count"], raw_marginal["avg_demand"], 1)[0]
skew = pd.DataFrame({
    "method": ["Skew-managed (current)", "No skew management"],
    "zones": [len(common_locations), pu["location_id"].nunique()],
    "closure_count_min": [marginal["closure_count"].min(), raw_marginal["construction_count"].min()],
    "closure_count_max": [marginal["closure_count"].max(), raw_marginal["construction_count"].max()],
    "baseline_rides_per_loc_hr": [baseline, raw_baseline],
    "change_per_closure_rides": [slope, raw_slope],
    "change_per_closure_pct": [slope / baseline * 100, raw_slope / raw_baseline * 100],
})

# ================================================================ EXPORT ====
print(f"Writing to {OUT}")

# --- dim_zone: names + centroid lat/lon + WKT + every per-zone metric ---
zones_wgs = zones.to_crs(epsg=4326)
centroids = zones.geometry.centroid.to_crs(epsg=4326)  # centroid in projected CRS, then reproject
geo = pd.DataFrame({
    "location_id": zones["LocationID"].astype(int),
    "latitude": centroids.y.round(6),
    "longitude": centroids.x.round(6),
    "area_sq_km": (zones.geometry.area * 0.09290304 / 1e6).round(4),  # EPSG:2263 is US feet
    "wkt": zones_wgs.geometry.simplify(0.0002, preserve_topology=True).to_wkt(),
}).drop_duplicates("location_id")

zone_rides = pu.groupby("location_id").agg(
    total_rides=("ride_count", "sum"), total_real_revenue=("revenue", "sum"),
    avg_trip_duration_sec=("avg_trip_duration", "mean"),
).reset_index()
zone_rides["avg_fare"] = zone_rides["total_real_revenue"] / zone_rides["total_rides"].replace(0, np.nan)
zone_closures = closures.groupby("location_id").size().rename("n_closures").reset_index()

dim_zone = (
    lookup.rename(columns={"LocationID": "location_id", "Borough": "borough", "Zone": "zone",
                           "service_zone": "service_zone"})
    .merge(geo, on="location_id", how="left")
    .merge(zone_rides, on="location_id", how="left")
    .merge(zone_closures, on="location_id", how="left")
    .merge(snap_wide, on="location_id", how="left")
    .merge(revenue, on="location_id", how="left")
)
dim_zone["in_cohort"] = dim_zone["location_id"].isin(common_locations)
dim_zone["total_real_revenue"] = dim_zone["total_real_revenue"].fillna(0.0)
fill0 = ["total_rides", "n_closures", "diff_3mo_total"] + [c for c in dim_zone if c.startswith("active_closures_")]
dim_zone[fill0] = dim_zone[fill0].fillna(0).astype(int)
dim_zone["effect_direction"] = np.select(
    [dim_zone["avg_pct_change"] > 0, dim_zone["avg_pct_change"] < 0], ["Increase", "Decrease"], "No data"
)
save_csv(dim_zone, "dim_zone.csv")

zones_wgs[["LocationID", "zone", "borough", "geometry"]].assign(
    geometry=zones_wgs.geometry.simplify(0.0001, preserve_topology=True)
).rename(columns={"LocationID": "location_id"}).to_file(OUT / "taxi_zones.geojson", driver="GeoJSON")
print(f"  {'taxi_zones.geojson':<34} {len(zones_wgs):>10,} shapes")

# --- dim_date ---
dates = pd.date_range(min(pu["date"].min(), closures["start_time"].min().normalize()),
                      max(pu["date"].max(), TODAY), freq="D")
dim_date = pd.DataFrame({"date": dates})
dim_date["year"] = dates.year
dim_date["month"] = dates.month
dim_date["month_name"] = dates.strftime("%b")
dim_date["year_month"] = dates.strftime("%Y-%m")
dim_date["quarter"] = "Q" + dates.quarter.astype(str)
dim_date["day_of_week"] = dates.dayofweek + 1  # 1 = Monday
dim_date["day_name"] = dates.strftime("%a")
dim_date["is_weekend"] = dates.dayofweek >= 5
save_csv(dim_date.assign(date=dim_date["date"].dt.date), "dim_date.csv")

# --- dim_closure_bucket ---
save_csv(pd.DataFrame({"closure_bucket": BUCKET_ORDER, "bucket_sort": range(len(BUCKET_ORDER))}),
         "dim_closure_bucket.csv")

# --- facts ---
fact_demand = pu.assign(
    closure_bucket=pu["closure_bucket"].astype(str), taxi_type=pu["taxi_type"].astype(str),
    date=pu["date"].dt.date,
)
fact_demand.to_parquet(OUT / "fact_demand.parquet", index=False)
print(f"  {'fact_demand.parquet':<34} {len(fact_demand):>10,} rows")

fact_closures = closures[["location_id", "borough", "start_time", "end_time"]].copy()
fact_closures["start_date"] = fact_closures["start_time"].dt.date
fact_closures["duration_days"] = ((fact_closures["end_time"] - fact_closures["start_time"]).dt.total_seconds()
                                  / 86400).round(2)
fact_closures["active_on_today"] = (fact_closures["start_time"] <= TODAY) & (
    fact_closures["end_time"].isna() | (fact_closures["end_time"] >= TODAY))
save_csv(fact_closures, "fact_closures.csv")

save_csv(snapshots[["location_id", "snapshot_month", "snapshot_date", "active_closures"]], "fact_closure_snapshots.csv")

save_csv(region_change.assign(closure_bucket=region_change["closure_bucket"].astype(str)),
         "fact_zone_bucket_effect.csv")

# --- summary tables ---
# Same cohort and baseline as section 3, but split into 0..AGG_MAX_BUCKET-1 and "N+".
fine = bucketed.assign(bucket_sort=bucketed["construction_count"].clip(upper=AGG_MAX_BUCKET).astype(int))
# Expected revenue per row = that zone's own 0-closure revenue rate, so the comparison
# isn't distorted by which zones happen to fall in each bucket.
fine = fine.merge(per_loc_base[["location_id", "baseline_revenue"]], on="location_id", how="left")
by_fine = fine.groupby("bucket_sort").agg(
    avg_demand=("ride_count", "mean"), n_obs=("ride_count", "size"), total_rides=("ride_count", "sum"),
    n_zones=("location_id", "nunique"), real_revenue=("revenue", "sum"),
    expected_revenue=("baseline_revenue", "sum"),
).reset_index()
by_fine["closure_bucket"] = by_fine["bucket_sort"].astype(str).where(
    by_fine["bucket_sort"] < AGG_MAX_BUCKET, f"{AGG_MAX_BUCKET}+")
by_fine["pct_change_vs_no_closure"] = (by_fine["avg_demand"] - baseline) / baseline * 100
by_fine["avg_revenue"] = by_fine["real_revenue"] / by_fine["n_obs"]
by_fine["avg_fare"] = by_fine["real_revenue"] / by_fine["total_rides"]
by_fine["revenue_vs_expected"] = by_fine["real_revenue"] - by_fine["expected_revenue"]
by_fine["revenue_vs_expected_pct"] = by_fine["revenue_vs_expected"] / by_fine["expected_revenue"] * 100
save_csv(by_fine[["closure_bucket", "bucket_sort", "avg_demand", "n_obs", "total_rides", "n_zones",
                  "pct_change_vs_no_closure", "avg_fare", "avg_revenue", "real_revenue", "expected_revenue",
                  "revenue_vs_expected", "revenue_vs_expected_pct"]], "agg_demand_by_bucket.csv")
save_csv(hourly.assign(closure_bucket=hourly["closure_bucket"].astype(str)), "agg_hourly_by_bucket.csv")
save_csv(raw_by_count, "agg_demand_by_closure_count.csv")
save_csv(skew, "skew_comparison.csv")

trip_start, trip_end = pu["date"].min(), pu["date"].max()
trip_months = (trip_end.year - trip_start.year) * 12 + trip_end.month - trip_start.month + 1
kpi = pd.DataFrame([
    ("cohort_zones", len(common_locations), "zones", "Zones observed at 0, 1 and 2 concurrent closures"),
    ("baseline_demand", baseline, "rides/location-hr", "Avg demand with 0 closures (cohort)"),
    ("marginal_change_per_closure", slope, "rides/location-hr", "Slope over 1..N-1 closures"),
    ("marginal_change_per_closure_pct", slope / baseline * 100, "%", "Slope as % of baseline"),
    ("total_incremental_rides", revenue["total_incremental_rides"].sum(), "rides", "Positive-shift zones"),
    ("total_revenue_gain", revenue["total_revenue_gain"].sum(), "USD", "Estimated gross revenue gain"),
    ("total_real_revenue", pu["revenue"].sum(), "USD", "Observed revenue, all zones and hours"),
    ("cohort_real_revenue_with_closures", overall_effect["real_revenue_with_closures"].sum(), "USD",
     "Observed revenue in cohort zone-hours with >=1 closure"),
    ("cohort_expected_revenue_with_closures", overall_effect["expected_revenue_with_closures"].sum(), "USD",
     "Same zone-hours at each zone's 0-closure revenue rate"),
    ("cohort_revenue_vs_expected", overall_effect["revenue_vs_expected"].sum(), "USD",
     "Real minus expected revenue during closures"),
    ("snapshot_today", TODAY.strftime("%Y-%m-%d"), "date", "Reference date for active closures"),
    # --- closure counts ---
    ("total_closures", len(closures), "closures", "Closure records (one per street segment / OFT code)"),
    ("distinct_closures", len(closures.drop_duplicates(["location_id", "start_time", "end_time"])), "closures",
     "Unique zone + start + end combinations (one per project per zone)"),
    ("closures_in_trip_period", int(((closures["start_time"] < trip_end + pd.Timedelta(days=1))
                                     & (closures["end_time"].isna() | (closures["end_time"] >= trip_start))).sum()),
     "closures", "Closure records overlapping the trip data period"),
    ("closures_active_today", int(((closures["start_time"] <= TODAY)
                                   & (closures["end_time"].isna() | (closures["end_time"] >= TODAY))).sum()),
     "closures", "Closure records active on snapshot_today"),
    ("zones_with_closures", closures["location_id"].nunique(), "zones", "Taxi zones with at least one closure"),
    # --- data period ---
    ("trip_data_start", trip_start.strftime("%Y-%m-%d"), "date", "First date in trip data"),
    ("trip_data_end", trip_end.strftime("%Y-%m-%d"), "date", "Last date in trip data"),
    ("trip_data_months", trip_months, "months", "Calendar months covered by trip data"),
    ("closure_data_start", closures["start_time"].min().strftime("%Y-%m-%d"), "date", "Earliest closure start"),
    ("closure_data_end", closures["start_time"].max().strftime("%Y-%m-%d"), "date", "Latest closure start"),
], columns=["metric", "value", "unit", "description"])
save_csv(kpi, "kpi_summary.csv")

print("\nCheck against analysis.ipynb:")
print(f"  baseline {baseline:.3f}  slope {slope:+.3f}  pct {slope / baseline * 100:+.2f}%  "
      f"revenue ${revenue['total_revenue_gain'].sum():,.2f}")
