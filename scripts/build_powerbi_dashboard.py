"""Power BI pack for the investor dashboard: construction closures vs. trip demand.

Run from anywhere:   python scripts/build_powerbi_dashboard.py
Inputs:              data/powerbi/          (from scripts/export_powerbi.py)
Outputs:             data/powerbi_dashboard/
    01_kpi_cards.csv               one row, one column per KPI card
    02_demand_by_closures.csv      column chart (page 1)
    03_hourly_profile.csv          line chart, long format (page 1)
    04_monthly_gap.csv             line chart, long format (page 2)
    05_closure_pipeline.csv        stacked column (page 2)
    06_zone_map.csv                shape map / bubble map (page 3)
    07_borough_summary.csv         bar chart (page 3)
    08_top_zones.csv               table (page 3)
    dim_borough.csv                optional slicer table (page 3)
    nyc_taxi_zones.topojson        custom map for the Shape Map visual
    investor_theme.json            Power BI report theme (View > Themes > Browse)

Every CSV uses display-ready column names, so a field dropped into a visual is already labelled.
Percentages are stored as decimals (0.22 = 22%) so Power BI's % format works directly.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from powerbi_style import (YELLOW, YELLOW_DARK, YELLOW_LIGHT, YELLOW_PALE, YELLOW_TEXT, BAD, BODY_FONT, EXTRA_SERIES,
                           GOOD, GRID, HEAD_FONT, HERO_FILL, HERO_LABEL, HERO_VALUE, HOURLY_COLOURS, INK, INK_2,
                           MAP_CENTER, MAP_HIGH, MAP_HIGH_MID, MAP_NODATA, MUTED, NUM_FONT, PAGE, SLATE, SLATE_BLUE,
                           SLATE_BLUE_MID, SURFACE, THEME_NAME, TITLE_FONT, fs, money, px)

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "powerbi"
OUT = ROOT / "data" / "powerbi_dashboard"
OUT.mkdir(parents=True, exist_ok=True)

FOLD_AT = 10
NYC_BOROUGHS = ["Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"]


def hx(c: str) -> tuple:
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def save(df: pd.DataFrame, name: str) -> pd.DataFrame:
    df.to_csv(OUT / name, index=False, encoding="utf-8-sig")  # BOM: Power BI reads UTF-8 cleanly
    print(f"  {name:<30} {len(df):>5} rows  ·  {', '.join(df.columns)[:90]}")
    return df


def diverging_hex(pct: float) -> str:
    """Revenue-vs-expected % -> fill colour (subway blue -> neutral -> taxi yellow, clipped at ±25%)."""
    if pd.isna(pct):
        return MAP_NODATA
    stops = [(-25, hx(SLATE_BLUE)), (-12.5, hx(SLATE_BLUE_MID)), (0, hx(MAP_CENTER)),
             (12.5, hx(MAP_HIGH_MID)), (25, hx(MAP_HIGH))]
    p = float(np.clip(pct, -25, 25))
    for (x0, c0), (x1, c1) in zip(stops, stops[1:]):
        if p <= x1:
            t = (p - x0) / (x1 - x0)
            return "#" + "".join(f"{round(a + (b - a) * t):02X}" for a, b in zip(c0, c1))
    return MAP_HIGH


# ============================================================================ load ====
print("Loading data/powerbi ...")
kpi = pd.read_csv(SRC / "kpi_summary.csv").set_index("metric")["value"]
K = lambda k: float(kpi[k])  # noqa: E731
by_bucket = pd.read_csv(SRC / "agg_demand_by_bucket.csv", dtype={"closure_bucket": str})
hourly = pd.read_csv(SRC / "agg_hourly_by_bucket.csv", dtype={"closure_bucket": str})
zones = pd.read_csv(SRC / "dim_zone.csv").drop(columns="wkt")
closures = pd.read_csv(SRC / "fact_closures.csv", parse_dates=["start_time", "end_time"])
skew = pd.read_csv(SRC / "skew_comparison.csv")
demand = pd.read_parquet(SRC / "fact_demand.parquet",
                         columns=["date", "ride_count", "construction_count", "in_cohort"])
demand["month"] = pd.to_datetime(demand["date"]).dt.to_period("M").dt.to_timestamp()
baseline = K("baseline_demand")
trip_end = pd.Timestamp(kpi["trip_data_end"])

print(f"Writing {OUT.relative_to(ROOT)}/ ...")

# ---------------------------------------------------- 02 demand by closure count ----
b = by_bucket.assign(n=by_bucket["bucket_sort"].clip(upper=FOLD_AT))
curve = b.groupby("n").agg(rides=("total_rides", "sum"), obs=("n_obs", "sum"), zones_=("n_zones", "max")).reset_index()
curve["avg"] = curve["rides"] / curve["obs"]
curve["uplift"] = curve["avg"] / baseline - 1
labelled = {1, 2, FOLD_AT}
demand_curve = save(pd.DataFrame({
    "Concurrent closures": np.where(curve["n"] >= FOLD_AT, f"{FOLD_AT}+", curve["n"].astype(str)),
    "Sort order": curve["n"],
    "Avg rides per zone-hour": curve["avg"].round(2),
    "Uplift vs no closures": curve["uplift"].round(4),
    "Uplift label": [f"+{u:.0%}" if n in labelled else "" for n, u in zip(curve["n"], curve["uplift"])],
    "Zones observed": curve["zones_"],
    "Zone-hours observed": curve["obs"],
    "Bar colour": np.where(curve["n"] == 0, SLATE, YELLOW),
    "Baseline": round(baseline, 2),
}), "02_demand_by_closures.csv")
uplift_1 = float(curve.loc[curve["n"] == 1, "uplift"].iloc[0])
uplift_2 = float(curve.loc[curve["n"] == 2, "uplift"].iloc[0])

# ---------------------------------------------------------- 03 hourly profile ----
series = {k: (name, i + 1, HOURLY_COLOURS[name])
          for i, (k, name) in enumerate([("0", "No closures"), ("1", "1 closure"), ("2", "2 closures"),
                                         ("3+", "3+ closures")])}
h = hourly.copy()
base_by_hour = h[h["closure_bucket"] == "0"].set_index("hour")["avg_demand_rides"]
h["Series"] = h["closure_bucket"].map(lambda k: series[k][0])
h["Series sort"] = h["closure_bucket"].map(lambda k: series[k][1])
h["Line colour"] = h["closure_bucket"].map(lambda k: series[k][2])
h["Hour"] = h["hour"].map(lambda x: f"{x:02d}:00")  # text that sorts correctly
h["Avg rides per zone-hour"] = h["avg_demand_rides"].round(2)
h["Uplift vs no closures"] = (h["avg_demand_rides"] / h["hour"].map(base_by_hour) - 1).round(4)
h["Avg revenue per zone-hour"] = h["avg_revenue"].round(2)
hourly_out = save(h[["Hour", "Series", "Series sort", "Avg rides per zone-hour", "Uplift vs no closures",
                     "Avg revenue per zone-hour", "Line colour"]].sort_values(["Series sort", "Hour"]),
                  "03_hourly_profile.csv")
one = h[h["closure_bucket"] == "1"].set_index("hour")["Uplift vs no closures"]
best_hour, best_hour_uplift = int(one.idxmax()), float(one.max())

# ------------------------------------------------------------- 04 monthly gap ----
coh = demand[demand["in_cohort"]].assign(has=lambda d: d["construction_count"] > 0)
m = coh.groupby(["month", "has"])["ride_count"].mean().unstack()
gap = m[True] / m[False] - 1
share = coh.groupby("month")["has"].mean()
monthly_long = pd.concat([
    pd.DataFrame({"Month": m.index, "Series": "Active closure", "Series sort": 1,
                  "Avg rides per zone-hour": m[True].round(2).values, "Gap vs no closure": gap.round(4).values}),
    pd.DataFrame({"Month": m.index, "Series": "No active closure", "Series sort": 2,
                  "Avg rides per zone-hour": m[False].round(2).values, "Gap vs no closure": np.nan}),
])
monthly_long["Share of zone-hours under construction"] = monthly_long["Month"].map(share).round(4)
monthly_long["Month"] = monthly_long["Month"].dt.date
save(monthly_long.sort_values(["Series sort", "Month"]), "04_monthly_gap.csv")
months_ahead, n_months, gap_median = int((gap > 0).sum()), len(gap), float(gap.median())
weak_month = gap.idxmin()

# -------------------------------------------------------- 05 closure pipeline ----
rows = []
for p in pd.period_range(kpi["closure_data_start"], kpi["snapshot_today"], freq="M"):
    m0, m1 = p.start_time, p.end_time
    act = closures[(closures["start_time"] <= m1) & (closures["end_time"].isna() | (closures["end_time"] >= m0))]
    new = closures[(closures["start_time"] >= m0) & (closures["start_time"] <= m1)]
    rows.append({"Month": m0.date(), "Period": "Within trip data" if m0 <= trip_end else "Forward pipeline",
                 "Active closures": len(act), "New closures": len(new),
                 "Zones affected": act["location_id"].nunique()})
pipeline = save(pd.DataFrame(rows), "05_closure_pipeline.csv")
last_pipe = pipeline.iloc[-1]

# ----------------------------------------------------------------- 06 zone map ----
z = zones[zones["borough"].isin(NYC_BOROUGHS)].copy()
z["Zone key"] = z["location_id"].map(lambda i: f"Z{i:03d}")
has = z["in_cohort"].astype(bool)
z_map = save(pd.DataFrame({
    "Zone key": z["Zone key"],
    "Zone": z["zone"],
    "Borough": z["borough"],
    "Latitude": z["latitude"].round(6),
    "Longitude": z["longitude"].round(6),
    "Revenue vs expected % (map)": (z["revenue_vs_expected_pct"].clip(-25, 25) / 100).where(has).round(4),
    "Revenue vs expected %": (z["revenue_vs_expected_pct"] / 100).where(has).round(4),
    "Revenue vs expected $": z["revenue_vs_expected"].where(has).round(0),
    "Demand change %": (z["avg_pct_change"] / 100).where(has).round(4),
    "Closures": z["n_closures"].astype(int),
    "Total rides": z["total_rides"],
    "Effect": np.where(has, z["effect_direction"], "Insufficient history"),
    "Fill colour": [diverging_hex(v) if c else MAP_NODATA for v, c in zip(z["revenue_vs_expected_pct"], has)],
}), "06_zone_map.csv")

# --------------------------------------------------------- 07 borough summary ----
c = z[has]
boro = (c.groupby("borough").agg(zones_=("location_id", "size"), closures_=("n_closures", "sum"),
                                 rev=("revenue_vs_expected", "sum"), med=("avg_pct_change", "median"),
                                 up=("effect_direction", lambda s: (s == "Increase").sum()))
        .reset_index().sort_values("rev", ascending=False))
boro_out = save(pd.DataFrame({
    "Borough": boro["borough"],
    "Revenue above expected $": boro["rev"].round(0),
    "Revenue label": boro["rev"].map(money),
    "Zones": boro["zones_"],
    "Closures": boro["closures_"].astype(int),
    "Share of zones with uplift": (boro["up"] / boro["zones_"]).round(4),
    "Median demand change": (boro["med"] / 100).round(4),
}), "07_borough_summary.csv")
save(pd.DataFrame({"Borough": NYC_BOROUGHS}), "dim_borough.csv")

# -------------------------------------------------------------- 08 top zones ----
top = c.nlargest(10, "revenue_vs_expected")
save(pd.DataFrame({
    "Rank": range(1, len(top) + 1),
    "Zone": top["zone"].values,
    "Borough": top["borough"].values,
    "Closures": top["n_closures"].astype(int).values,
    "Demand change": (top["avg_pct_change"] / 100).round(4).values,
    "Excess revenue": top["revenue_vs_expected"].round(0).values,
}), "08_top_zones.csv")

# --------------------------------------------------------------- 01 KPI cards ----
total_rides = int(demand["ride_count"].sum())
share_up = float((c["effect_direction"] == "Increase").mean())
kpis = save(pd.DataFrame([{
    "Trips analysed": total_rides,
    "Fare revenue analysed": round(K("total_real_revenue")),
    "Closures mapped": int(K("total_closures")),
    "Demand uplift, first closure": round(uplift_1, 4),
    "Revenue above expected": round(K("cohort_revenue_vs_expected")),
    "Zones with higher demand": round(share_up, 4),
    "Comparable zones": int(K("cohort_zones")),
    "Uplift per extra closure": round(K("marginal_change_per_closure_pct") / 100, 4),
    "Trip data period": f"{pd.Timestamp(kpi['trip_data_start']):%b %Y} – {trip_end:%b %Y}",
    "Zones with closures": int(K("zones_with_closures")),
    "Pooled slope per closure": round(float(skew.iloc[1]["change_per_closure_pct"]) / 100, 4),
}]), "01_kpi_cards.csv")

# ---------------------------------------------------------------- TopoJSON ----
gj = json.loads((SRC / "taxi_zones.geojson").read_text(encoding="utf-8"))
arcs, geoms = [], []


def ring_arc(ring):
    arcs.append([[round(x, 5), round(y, 5)] for x, y in ring])
    return len(arcs) - 1


for f in gj["features"]:
    if f["properties"]["borough"] not in NYC_BOROUGHS:
        continue
    g = f["geometry"]
    if g["type"] == "Polygon":
        topo_arcs = [[ring_arc(r)] for r in g["coordinates"]]
    else:
        topo_arcs = [[[ring_arc(r)] for r in poly] for poly in g["coordinates"]]
    lid = int(f["properties"]["location_id"])
    geoms.append({"type": g["type"], "arcs": topo_arcs,
                  "properties": {"zone_key": f"Z{lid:03d}", "zone": f["properties"]["zone"],
                                 "borough": f["properties"]["borough"]}})
topo = {"type": "Topology", "objects": {"taxi_zones": {"type": "GeometryCollection", "geometries": geoms}},
        "arcs": arcs}
(OUT / "nyc_taxi_zones.topojson").write_text(json.dumps(topo, separators=(",", ":")), encoding="utf-8")
print(f"  nyc_taxi_zones.topojson        {len(geoms)} zones")


# ------------------------------------------------------------------- theme ----
solid = lambda col: {"solid": {"color": col}}  # noqa: E731
ZERO_PAD = [{"top": 0, "bottom": 0, "left": 0, "right": 0}]
NO_CHROME = {"background": [{"show": False}], "border": [{"show": False}], "title": [{"show": False}],
             "dropShadow": [{"show": False}], "padding": ZERO_PAD}
theme = {
    "name": THEME_NAME,
    "dataColors": [YELLOW, SLATE, YELLOW_LIGHT, YELLOW_DARK, SLATE_BLUE, INK, *EXTRA_SERIES],
    "background": SURFACE, "foreground": INK, "tableAccent": YELLOW,
    "foregroundNeutralSecondary": INK_2, "foregroundNeutralTertiary": MUTED,
    "backgroundLight": GRID, "backgroundNeutral": GRID, "backgroundDark": PAGE,
    "good": GOOD, "neutral": SLATE, "bad": BAD,
    "maximum": MAP_HIGH, "center": MAP_CENTER, "minimum": SLATE_BLUE,
    "textClasses": {
        "callout": {"fontSize": fs(26), "fontFace": NUM_FONT, "color": INK},
        "title": {"fontSize": fs(13), "fontFace": TITLE_FONT, "color": INK},
        "header": {"fontSize": fs(12), "fontFace": TITLE_FONT, "color": INK},
        "label": {"fontSize": fs(10), "fontFace": BODY_FONT, "color": INK_2},
    },
    "visualStyles": {
        "*": {"*": {
            "background": [{"show": True, "color": solid(SURFACE), "transparency": 0}],
            "border": [{"show": True, "color": solid(GRID), "radius": px(12)}],
            "dropShadow": [{"show": False}],
            "padding": [{"top": px(12), "bottom": px(12), "left": px(14), "right": px(14)}],
            "title": [{"show": True, "fontColor": solid(INK), "fontSize": fs(13), "fontFamily": TITLE_FONT,
                       "alignment": "left"}],
            "subTitle": [{"show": True, "fontColor": solid(INK_2), "fontSize": fs(10), "fontFamily": BODY_FONT}],
            "categoryAxis": [{"labelColor": solid(MUTED), "titleColor": solid(MUTED), "gridlineShow": False,
                              "fontSize": fs(10), "fontFamily": BODY_FONT}],
            "valueAxis": [{"labelColor": solid(MUTED), "titleColor": solid(MUTED), "gridlineShow": True,
                           "gridlineColor": solid(GRID), "gridlineStyle": "solid", "fontSize": fs(10),
                           "fontFamily": BODY_FONT}],
            "legend": [{"show": True, "position": "TopLeft", "showTitle": False, "labelColor": solid(INK_2),
                        "fontSize": fs(10), "fontFamily": BODY_FONT}],
            "visualHeader": [{"show": False}],
            "visualTooltip": [{"background": solid(SURFACE), "titleFontColor": solid(MUTED),
                               "valueFontColor": solid(INK)}],
        }},
        "page": {"*": {"background": [{"color": solid(PAGE), "transparency": 0}],
                       "outspace": [{"color": solid(PAGE)}]}},
        "textbox": {"*": NO_CHROME},
        "shape": {"*": NO_CHROME},
        "basicShape": {"*": NO_CHROME},
        "slicer": {"*": {**NO_CHROME, "header": [{"show": False}],
                         "items": [{"fontColor": solid(INK_2), "background": solid(SURFACE), "fontSize": fs(10),
                                    "fontFamily": BODY_FONT}]}},
        "card": {"*": {"labels": [{"color": solid(INK), "fontSize": fs(26), "fontFamily": NUM_FONT}],
                       "categoryLabels": [{"color": solid(MUTED), "fontSize": fs(9), "fontFamily": BODY_FONT}],
                       "padding": [{"top": px(10), "bottom": px(10), "left": px(14), "right": px(14)}]}},
        "tableEx": {"*": {"grid": [{"gridVertical": False, "gridHorizontal": True,
                                    "gridHorizontalColor": solid(GRID), "rowPadding": px(4)}],
                          "columnHeaders": [{"fontColor": solid(MUTED), "backColor": solid(SURFACE),
                                             "fontSize": fs(10), "fontFamily": TITLE_FONT}],
                          "values": [{"fontColorPrimary": solid(INK), "backColorPrimary": solid(SURFACE),
                                      "backColorSecondary": solid(SURFACE), "fontSize": fs(10),
                                      "fontFamily": BODY_FONT}]}},
    },
}
(OUT / "investor_theme.json").write_text(json.dumps(theme, indent=2), encoding="utf-8")
print("  investor_theme.json")

print("Done.")
