"""Shared palette, fonts and page layout for the Power BI report.

Imported by build_powerbi_dashboard.py (theme) and build_powerbi_preview.py (HTML mock-up),
so the theme and the preview always use the same numbers.

Theme "Yellow Cab · Night": NYC taxi yellow on asphalt black, like a cab under streetlights.
Yellow = closures, grey = no closures, everywhere. The map diverges taxi yellow (above expected) to subway blue (below).
On the dark ground, brighter yellow means more closures. The hero KPI is a solid yellow panel with black type (cab door).
"""

# ------------------------------------------------------------------ colours ----
THEME_NAME = "Yellow Cab · Night"
INK = "#F4F4EF"          # off-white ink: headlines, values
INK_2 = "#BEBEB6"        # body text, subtitles
MUTED = "#8C8C85"        # axis labels, captions, card labels
GRID = "#2F2F2F"         # gridlines, card borders
SURFACE = "#1B1B1B"      # visual background (cards)
PAGE = "#0F0F0F"         # page background (asphalt black)

YELLOW = "#F7B500"        # primary series: active closures (NYC taxi yellow)
YELLOW_LIGHT = "#FFD54A"  # 3+ closures
YELLOW_DARK = "#B08000"   # 1 closure (dimmest yellow)
YELLOW_PALE = "#5A4600"   # forward pipeline, table data bars (muted yellow on dark)
YELLOW_TEXT = "#FFC72C"   # small yellow text on cards (kickers)
SLATE = "#8F959C"        # baseline / no closures (concrete grey)
SLATE_BLUE = "#5E8FD0"   # map: below expected (subway blue)
SLATE_BLUE_MID = "#4B6384"  # map: halfway to below
MAP_HIGH = "#FFC20E"     # map: above expected
MAP_HIGH_MID = "#9B7D23"  # map: halfway to above
MAP_CENTER = "#383838"   # map: on expectation
MAP_NODATA = "#242424"   # map: insufficient history
MAP_LINE = PAGE          # map: zone borders
HERO_FILL = YELLOW       # hero KPI card background (cab-door yellow)
HERO_VALUE = "#111111"   # hero KPI value (black on yellow)
HERO_LABEL = "#4A3A00"   # card label on the hero card
GOOD = "#5FAF85"
BAD = "#D9705F"
EXTRA_SERIES = ["#6FA893", BAD]  # spare data colours after the yellow/grey set

# Series colours used in the CSVs (field-value colouring)
HOURLY_COLOURS = {"No closures": SLATE, "1 closure": YELLOW_DARK, "2 closures": YELLOW, "3+ closures": YELLOW_LIGHT}

# -------------------------------------------------------------------- fonts ----
HEAD_FONT = "DIN"                # page headlines (street-sign feel), insight / method headings
BODY_FONT = "Segoe UI"           # everything else
TITLE_FONT = "Segoe UI Semibold"  # visual titles
NUM_FONT = "DIN"                 # KPI callouts (Power BI built-in font list)

# ------------------------------------------------------------------- layout ----
PT_PX = 4 / 3
# Canvas 1920 x 1080 (Power BI custom page size). The layout below is designed on a 1280 x 720 grid
# (outer margin 24, gutter 16) and every size is multiplied by SCALE, so the page looks the same, just with more pixels.
# Power BI font sizes are points: on the canvas 1 pt = 4/3 px (PT_PX), which the preview uses to predict wrapping.
# Each row: (id, component, Power BI object, x, y, w, h), in design-grid units.
BASE_W, BASE_H = 1280, 720
CANVAS_W, CANVAS_H = 1920, 1080
SCALE = CANVAS_W / BASE_W


def px(v: float) -> int:
    """Design-grid pixels -> canvas pixels (rounded half up)."""
    return int(v * SCALE + 0.5)


def fs(v: float) -> int:
    """Design font size in points -> canvas font size in whole points (Power BI's format pane takes whole numbers)."""
    return int(v * SCALE + 0.5)


def _row(i, name, kind, x, y, w, h):
    return {"id": i, "name": name, "kind": kind, "x": px(x), "y": px(y), "w": px(w), "h": px(h)}


KPI_NAMES = ["Trips analysed", "Fare revenue analysed", "Closures mapped",
             "Demand uplift, first closure", "Revenue above expected", "Zones with higher demand"]
HERO_KPI = 3  # zero-based index of the yellow highlight card

LAYOUT = {
    1: [
        _row("A1", "Accent rule", "Shape · Rectangle", 24, 20, 8, 72),
        _row("T1", "Headline + lede", "Text box", 44, 16, 876, 80),
        _row("T2", "Context", "Text box", 936, 16, 320, 80),
        *[_row(f"K{i+1}", f"KPI card · {n}", "Card", 24 + 208 * i, 112, 192, 80) for i, n in enumerate(KPI_NAMES)],
        *[_row(f"I{i+1}", f"Insight box {i+1}", "Text box", 24 + 416 * i, 208, 400, 104) for i in range(3)],
        _row("C1", "Demand curve", "Clustered column chart", 24, 328, 720, 376),
        _row("C2", "Hourly profile", "Line chart", 760, 328, 496, 376),
    ],
    2: [
        _row("A1", "Accent rule", "Shape · Rectangle", 24, 20, 8, 48),
        _row("T1", "Page title + dek", "Text box", 44, 16, 1212, 56),
        _row("C1", "Monthly gap", "Line chart", 24, 88, 1232, 296),
        _row("C2", "Closure pipeline", "Stacked column chart", 24, 400, 1232, 280),
        _row("T2", "Footnote", "Text box", 24, 684, 1232, 20),
    ],
    3: [
        _row("A1", "Accent rule", "Shape · Rectangle", 24, 20, 8, 48),
        _row("T1", "Page title + dek", "Text box", 44, 16, 676, 56),
        _row("S1", "Borough slicer", "Slicer", 736, 24, 520, 40),
        _row("C1", "Zone map", "Shape map", 24, 88, 620, 616),
        _row("C2", "By borough", "Clustered bar chart", 660, 88, 596, 248),
        _row("C3", "Top zones", "Table", 660, 352, 596, 352),
    ],
    4: [
        _row("A1", "Accent rule", "Shape · Rectangle", 24, 20, 8, 48),
        _row("T1", "Page title + dek", "Text box", 44, 16, 1212, 56),
        *[_row(f"M{i+1}", f"Method card {i+1}", "Text box", 24 + 624 * (i % 2), 88 + 210 * (i // 2), 608, 194)
          for i in range(6)],
    ],
}


def box(page: int, cid: str) -> dict:
    return next(r for r in LAYOUT[page] if r["id"] == cid)


def layout_table(page: int) -> str:
    """Markdown table of every object on a page, in build order."""
    lines = ["| ID | Component | Power BI object | x | y | w | h |", "|---|---|---|---:|---:|---:|---:|"]
    lines += [f"| {r['id']} | {r['name']} | {r['kind']} | {r['x']} | {r['y']} | {r['w']} | {r['h']} |"
              for r in LAYOUT[page]]
    return "\n".join(lines)


# --------------------------------------------------------------------- copy ----
def money(v: float) -> str:
    a = abs(v)
    s = f"${a/1e9:.1f}B" if a >= 1e9 else f"${a/1e6:.0f}M" if a >= 1e6 else f"${a/1e3:.0f}K"
    return ("-" if v < 0 else "") + s


def report_copy(s: dict) -> dict:
    """Every piece of on-canvas text, filled from the current numbers.

    Line lengths are budgeted against the box widths above at real Power BI sizes, so nothing wraps a single word
    onto its own line. If you edit copy, re-run build_powerbi_preview.py and check the wrap.
    """
    # Each number is stated once as a claim. KPI cards carry the headline figures, insight boxes add what the cards
    # can't show, chart titles say what is plotted, and subtitles add the one detail the chart needs.
    months_note = (f"{s['weak_month']} was the only month without a lead."
                   if s["n_months"] - s["months_ahead"] == 1
                   else f"Closure zones led in {s['months_ahead']} of {s['n_months']} months.")
    return {
        # page 1
        "headline": "Construction-related street closures concentrate ride demand",
        "lede": ["Zones with active construction closures record more trips and fare revenue than the same zones without them.",
                 "Closure permits are filed in advance, which makes them a leading indicator of demand."],
        "context": [f"Trip data · {s['period']}",
                    f"{s['cohort_zones']} comparable zones · {s['zones_with_closures']} zones with closures",
                    "Sources: NYC TLC trip records · NYC DOT closures"],
        # (number, heading, body). None of these repeat a KPI card value.
        "insights": [
            ("01", "The lift levels off after two closures",
             f"With three or more closures, demand stays {s['plateau_lo']:.0%}–{s['plateau_hi']:.0%} above "
             "baseline but does not keep rising."),
            ("02", f"Higher in {s['months_ahead']} of {s['n_months']} months",
             f"Median monthly gap of +{s['gap_median']:.0%}, widening through 2026."),
            ("03", f"{s['top_boro']} contributes {s['top_boro_rev']}",
             f"That is {s['top_boro_share']:.0%} of the revenue above expected. {s['second_boro']} is second "
             f"at {s['second_boro_rev']}."),
        ],
        "c_curve": ("Demand by number of concurrent closures",
                    "Average rides per zone-hour. Labels show the change relative to no closures."),
        "c_hourly": ("Demand by hour of day",
                     f"Higher at every hour; the largest lift is at {s['hour_lbl']} (+{s['best_hour_uplift']:.0%})."),
        # page 2
        "p2": ("The lift is consistent from month to month",
               "Monthly demand in comparable zones, and the construction closures active each month."),
        "c_monthly": ("Monthly demand, with and without an active closure",
                      f"Average rides per zone-hour in comparable zones. {months_note}"),
        "c_pipeline": ("Active construction closures by month",
                       "Permits are filed before work starts, so upcoming closures are known ahead of demand. "
                       f"{s['last_pipe_n']:,} active in {s['last_pipe_month']}."),
        "footnote": "Early 2025 is understated because closures that started before the record window aren't included.",
        # page 3
        "p3": ("Where closure hours earn more than expected",
               "Fare revenue during closure hours compared with each zone's own no-closure run-rate."),
        "c_map": ("Revenue vs. expected by zone",
                  "Yellow = above its own no-closure rate · blue = below · grey = insufficient history"),
        "c_boro": ("By borough", "Sum of zone-level revenue above expected"),
        "c_table": ("Top 10 zones", ""),
        # page 4
        "p4": ("Methodology & caveats", "Data sources, definitions and limitations."),
        "methods": [
            ("01", "Unit of analysis",
             f"Zone × hour × service (yellow, green, HVFHV), {s['period']}. Each zone-hour records trips, fare revenue "
             "and the number of active construction closures, mapped from NYC DOT records to TLC taxi zones."),
            ("02", "Like-for-like cohort",
             f"Headline effects use the {s['cohort_zones']} zones observed at 0, 1 and 2 concurrent closures, so each "
             "zone is compared against itself. Pooling every zone without that control flattens the slope to "
             f"{s['pooled']:+.1%} per closure, because dense zones with many closures mix with quiet outer zones."),
            ("03", "Expected revenue",
             "Closure zone-hours × that zone's own average revenue per zone-hour with no closures. Revenue above "
             "expected is actual fare revenue minus this amount."),
            ("04", "Association, not causation",
             "Closures tend to occur where activity is already increasing, such as areas of new development. The "
             "results describe a leading indicator of demand, not a causal effect."),
            ("05", "Data limitations",
             "Closures that began before the record window are excluded, so early 2025 closure activity is "
             "understated. Zones without history at 0, 1 and 2 closures are left out of the effect estimates."),
            ("06", "Next steps",
             "Add hour-of-week and weather controls, then back-test the closure pipeline to check whether permits "
             "filed in one month predict the following month's demand by zone."),
        ],
    }
