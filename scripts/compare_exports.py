"""Compare two exports of data/powerbi/ table by table.

Use it to check that a change to the SQL (or to the pipeline) didn't change any numbers:

    cp -r data/powerbi data/powerbi_baseline      # before the change
    python scripts/export_powerbi.py              # after the change
    python scripts/compare_exports.py data/powerbi_baseline data/powerbi

For each file it checks the column names and order, the row count, and every value.
Numbers must match within 1e-9 relative to the value, or 1e-9 relative to the largest value
in the column. The second allowance covers numbers near zero that come from subtracting
two large sums (e.g. real minus expected revenue of ~$3B), where engines legitimately
differ by fractions of a cent. Rows must be in the same order, except in fact tables,
where row order is meaningless; those are compared after sorting.
Exits with status 1 if any file differs.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RTOL, ATOL = 1e-9, 1e-9
UNORDERED = {"fact_demand.parquet"}


def as_numeric(s):
    """The column as floats if every non-missing value is a number, else None."""
    num = pd.to_numeric(s, errors="coerce")
    return num.astype(float) if num.notna().sum() == s.notna().sum() else None


def column_diffs(a, b):
    """Row positions where the two columns disagree."""
    na, nb = as_numeric(a), as_numeric(b)
    if na is not None and nb is not None:
        scale = max(np.nanmax(np.abs(na), initial=0), np.nanmax(np.abs(nb), initial=0))
        same = np.isclose(na, nb, rtol=RTOL, atol=max(ATOL, RTOL * scale), equal_nan=True)
    else:
        # Mixed column (e.g. kpi_summary.value): compare numerically where both sides parse.
        fa, fb = pd.to_numeric(a, errors="coerce"), pd.to_numeric(b, errors="coerce")
        both = fa.notna() & fb.notna()
        same = np.where(both, np.isclose(fa.fillna(0), fb.fillna(0), rtol=RTOL, atol=ATOL),
                        (a.astype(str) == b.astype(str)) | (a.isna() & b.isna()))
    return np.flatnonzero(~np.asarray(same, dtype=bool))


def compare_frames(name, a, b):
    problems = []
    if list(a.columns) != list(b.columns):
        problems.append(f"columns differ\n      baseline:  {list(a.columns)}\n      candidate: {list(b.columns)}")
        return problems
    if len(a) != len(b):
        problems.append(f"row count {len(a):,} vs {len(b):,}")
        return problems
    # A whole-number column turning into floats changes the CSV text ("947" -> "947.0").
    for col in a.columns:
        if pd.api.types.is_integer_dtype(a[col]) != pd.api.types.is_integer_dtype(b[col]):
            problems.append(f"{col}: type {a[col].dtype} vs {b[col].dtype}")
    if name in UNORDERED:
        a = a.sort_values(list(a.columns), ignore_index=True)
        b = b.sort_values(list(b.columns), ignore_index=True)
    for col in a.columns:
        bad = column_diffs(a[col].reset_index(drop=True), b[col].reset_index(drop=True))
        if len(bad):
            i = bad[0]
            problems.append(f"{col}: {len(bad):,} values differ, first at row {i}: "
                            f"{a[col].iloc[i]!r} vs {b[col].iloc[i]!r}")
    return problems


def load(path):
    if path.suffix == ".csv":
        return pd.read_csv(path, low_memory=False)
    if path.suffix == ".parquet":
        df = pd.read_parquet(path)
        for col in df.select_dtypes(include=["object", "string"]).columns:
            df[col] = df[col].astype(str)
        return df
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()

    names = sorted({p.name for p in args.baseline.iterdir()} | {p.name for p in args.candidate.iterdir()})
    failed = 0
    for name in names:
        a_path, b_path = args.baseline / name, args.candidate / name
        if not a_path.exists() or not b_path.exists():
            problems = [f"only in {'candidate' if not a_path.exists() else 'baseline'}"]
        elif a_path.suffix == ".geojson":
            same = json.loads(a_path.read_text(encoding="utf-8")) == json.loads(b_path.read_text(encoding="utf-8"))
            problems = [] if same else ["GeoJSON content differs"]
        else:
            a, b = load(a_path), load(b_path)
            problems = [] if a is None else compare_frames(name, a, b)
        failed += bool(problems)
        print(f"{'OK  ' if not problems else 'DIFF'}  {name}")
        for p in problems:
            print(f"      {p}")
    print(f"\n{len(names) - failed} of {len(names)} files match.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
