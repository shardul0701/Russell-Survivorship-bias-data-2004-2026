"""Check whether Norgate constituent data is available for Russell PIT builds."""

from __future__ import annotations

import argparse
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PARQUET_DIR = Path(r"C:\Users\shard\Light Water Internship\july-backtester-norgate-data\data")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet-data-dir", default=str(DEFAULT_PARQUET_DIR))
    parser.add_argument("--sample-symbol", default="AAPL")
    parser.add_argument("--index-name", default="Russell 3000")
    parser.add_argument("--start-date", default="2004-01-01")
    parser.add_argument("--end-date", default="2026-12-31")
    args = parser.parse_args()

    try:
        import norgatedata
    except ImportError:
        print("FAIL: Python package 'norgatedata' is not installed.")
        print("Run: python -m pip install --user norgatedata")
        return 1

    print(f"norgatedata package: {getattr(norgatedata, '__version__', 'unknown')}")
    if not norgatedata.status():
        print("FAIL: Norgate Data Updater is not reachable.")
        print("Open/start Norgate Data Updater on this PC, wait for it to report ready, then rerun this script.")
        return 2

    print("OK: Norgate Data Updater is reachable.")

    try:
        df = norgatedata.index_constituent_timeseries(
            args.sample_symbol,
            args.index_name,
            start_date=args.start_date,
            end_date=args.end_date,
            padding_setting=norgatedata.PaddingType.NONE,
            timeseriesformat="pandas-dataframe",
        )
    except Exception as exc:
        print(f"FAIL: constituent query failed for {args.sample_symbol} / {args.index_name}: {exc}")
        print("This usually means the Norgate subscription/export does not include historical index constituents.")
        return 3

    if df is None or len(df) == 0:
        print(f"FAIL: constituent query returned no rows for {args.sample_symbol} / {args.index_name}.")
        return 4

    print(f"OK: constituent query returned {len(df)} rows for {args.sample_symbol} / {args.index_name}.")
    print(df.head())

    parquet_dir = Path(args.parquet_data_dir)
    candidate_arg = f'--parquet-data-dir "{parquet_dir}"' if parquet_dir.is_dir() else '--candidate-database "US Equities" --candidate-database "US Equities Delisted"'
    for index_name in ("Russell 3000", "Russell 2000", "Russell 1000"):
        print()
        print(
            "python scripts\\build_from_norgate.py "
            f'--index "{index_name}" '
            f'--start-date "{args.start_date}" '
            f'--end-date "{args.end_date}" '
            f"{candidate_arg} "
            "--progress-every 250"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
