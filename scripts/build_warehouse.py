"""Build the DuckDB warehouse from the processed data, using the SQL in sql/.

Run from anywhere:   python scripts/build_warehouse.py
Output:              data/warehouse.duckdb

The SQL files run in layer order (staging -> intermediate -> marts) and in file-name order
within each layer. Each file is plain DuckDB SQL that creates its own tables, so you can
also open the warehouse and query it directly:

    duckdb data/warehouse.duckdb -c "SELECT * FROM skew_comparison"

Analysis parameters live in PARAMS below. The SQL reads them with getvariable('<name>').
"""

from datetime import datetime
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql"
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"
LAYERS = ("staging", "intermediate", "marts")

# ------------------------------------------------ parameters (match analysis.ipynb) ----
SNAPSHOT_TODAY = datetime(2026, 8, 31)
PARAMS = {
    "min_location_rides": 0,       # cohort: min rides a zone needs at each closure level
    "max_closure_bucket": 3,       # closure counts >= this pool into "3+"
    "require_top_bucket": False,   # cohort: also require the pooled "3+" level
    "agg_max_bucket": 20,          # finer bucketing for agg_demand_by_bucket only: 0..19, "20+"
    "snapshot_today": SNAPSHOT_TODAY,
    # month-end dates for the active-closure snapshots (section 5); the last one is "today"
    "snapshot_dates": [datetime(2026, 5, 31), datetime(2026, 6, 30), datetime(2026, 7, 31), SNAPSHOT_TODAY],
}


def sql_files():
    for layer in LAYERS:
        yield from sorted((SQL_DIR / layer).glob("*.sql"))


def build(db_path: Path = WAREHOUSE) -> duckdb.DuckDBPyConnection:
    """Rebuild the warehouse from scratch and return an open connection to it."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # Everything in it is derived, so start fresh: replacing tables in an existing file
    # doesn't shrink it.
    for stale in (db_path, db_path.with_name(db_path.name + ".wal")):
        stale.unlink(missing_ok=True)
    con = duckdb.connect(str(db_path))
    # Paths inside the SQL (e.g. 'data/processed/pu_agg.parquet') resolve against the repo root.
    con.execute(f"SET file_search_path = '{ROOT.as_posix()}'")
    for name, value in PARAMS.items():
        con.execute(f"SET VARIABLE {name} = $value", {"value": value})

    print(f"Building {db_path.relative_to(ROOT)} ...")
    for path in sql_files():
        con.execute(path.read_text(encoding="utf-8"))
        print(f"  {path.relative_to(SQL_DIR).as_posix()}")
    return con


if __name__ == "__main__":
    con = build()
    tables = con.execute("""
        SELECT table_name, table_type FROM information_schema.tables
        WHERE table_schema = 'main' ORDER BY table_name
    """).fetchall()
    print(f"\n{len(tables)} tables and views:")
    for name, kind in tables:
        rows = con.execute(f"SELECT COUNT(*) FROM {name}").fetchall()[0][0]
        print(f"  {name:<34} {rows:>10,} rows{'  (view)' if kind == 'VIEW' else ''}")
    con.close()
