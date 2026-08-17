"""Build Russell point-in-time YAML files from Norgate historical membership.

NON-RUNNABLE AS OF 2026-08-17 (issue #68) -- kept for documentation, not use.
This script requires a live Norgate Data Updater session and a Norgate Stocks
subscription with historical index constituents. That subscription has since
lapsed; the parquet export under Norgate's `TICKER-YYYYMM` delisted-security
naming (see scripts/census_delisted_coverage.py) is the surviving artifact of
it, not a live data source. Nobody on this project can log in to Norgate to
run this script, now or later, so "blocked pending access" no longer applies
-- it is closed. See the "Build From Norgate" section of README.md and issue
#68 for the rule-based-universe path (issue #70) that replaces it.

This script intentionally uses Norgate's index_constituent_timeseries API, not
the exported OHLCV parquet files. Price bars and breadth series cannot tell us
which stocks belonged to the index on each historical date.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import pandas as pd
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]

INDEX_CONFIG = {
    "russell1000": {
        "names": {"russell1000", "russell 1000", "rui", "$rui"},
        "norgate_name": "Russell 1000",
        "folder": "russell_1000_ticker_history",
        "file_prefix": "russell-1000-ticker-changes",
        "min_members": 850,
        "max_members": 1250,
    },
    "russell2000": {
        "names": {"russell2000", "russell 2000", "rut", "rty", "$rut"},
        "norgate_name": "Russell 2000",
        "folder": "russell_2000_ticker_history",
        "file_prefix": "russell-2000-ticker-changes",
        "min_members": 1500,
        "max_members": 2300,
    },
    "russell3000": {
        "names": {"russell3000", "russell 3000", "rua", "$rua"},
        "norgate_name": "Russell 3000",
        "folder": "russell_3000_ticker_history",
        "file_prefix": "russell-3000-ticker-changes",
        "min_members": 2400,
        "max_members": 3600,
    },
}


def clean_symbol(symbol: object) -> str:
    return str(symbol).strip().upper()


def normalize_index(index: str) -> str:
    key = str(index).strip().lower().replace("-", "").replace("_", "")
    for canonical, cfg in INDEX_CONFIG.items():
        normalized_names = {name.replace("-", "").replace("_", "") for name in cfg["names"]}
        if key in normalized_names:
            return canonical
    raise ValueError(f"Unsupported index {index!r}; use Russell 1000, Russell 2000, or Russell 3000.")


def candidate_symbols(args: argparse.Namespace) -> list[str]:
    symbols: set[str] = set()

    for path_str in args.symbols_file or []:
        path = Path(path_str)
        if not path.exists():
            raise FileNotFoundError(path)
        if path.suffix.lower() == ".json":
            symbols.update(clean_symbol(s) for s in json.loads(path.read_text(encoding="utf-8")))
        else:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip() and not line.lower().startswith("symbol"):
                    symbols.add(clean_symbol(line.split(",")[0]))

    for data_dir_str in args.parquet_data_dir or []:
        data_dir = Path(data_dir_str)
        if not data_dir.is_dir():
            raise FileNotFoundError(data_dir)
        for path in data_dir.glob("*.parquet"):
            name = path.stem
            if name.startswith(("#", "$")):
                continue
            symbols.add(clean_symbol(name))

    if args.candidate_database or args.candidate_watchlist:
        try:
            import norgatedata
        except ImportError as exc:
            raise RuntimeError("norgatedata is required for Norgate candidate lists.") from exc

        for database in args.candidate_database or []:
            symbols.update(clean_symbol(s) for s in norgatedata.database_symbols(database))
        for watchlist in args.candidate_watchlist or []:
            symbols.update(clean_symbol(s) for s in norgatedata.watchlist_symbols(watchlist))

    if not symbols:
        raise ValueError(
            "No candidate symbols. Use --candidate-database, --candidate-watchlist, "
            "--symbols-file, or --parquet-data-dir."
        )

    return sorted(symbols)


def membership_series(symbol: str, index_name: str, start_date: str, end_date: str) -> pd.Series:
    import norgatedata

    df = norgatedata.index_constituent_timeseries(
        symbol,
        index_name,
        start_date=start_date,
        end_date=end_date,
        padding_setting=norgatedata.PaddingType.NONE,
        timeseriesformat="pandas-dataframe",
    )
    if df is None or len(df) == 0:
        return pd.Series(dtype="int8")
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame(df)

    numeric_cols = [
        col for col in df.columns
        if pd.api.types.is_bool_dtype(df[col]) or pd.api.types.is_numeric_dtype(df[col])
    ]
    if len(numeric_cols) == 1:
        series = df[numeric_cols[0]]
    elif "Index Constituent" in df.columns:
        series = df["Index Constituent"]
    else:
        series = df.iloc[:, -1]

    series.index = pd.to_datetime(series.index).normalize()
    series = series.loc[(series.index >= pd.Timestamp(start_date)) & (series.index <= pd.Timestamp(end_date))]
    return series.fillna(0).astype("int8")


def build_daily_membership(
    symbols: Iterable[str],
    index_name: str,
    start_date: str,
    end_date: str,
    progress_every: int,
) -> dict[pd.Timestamp, set[str]]:
    daily: dict[pd.Timestamp, set[str]] = defaultdict(set)
    symbols = list(symbols)
    failures: list[tuple[str, str]] = []

    for i, symbol in enumerate(symbols, 1):
        if progress_every and (i == 1 or i % progress_every == 0):
            print(f"[{i}/{len(symbols)}] scanning {symbol}", flush=True)
        try:
            series = membership_series(symbol, index_name, start_date, end_date)
        except Exception as exc:
            failures.append((symbol, str(exc)))
            continue
        member_dates = series.index[series.astype(bool)]
        for dt in member_dates:
            daily[pd.Timestamp(dt).normalize()].add(symbol)

    if failures:
        fail_path = REPO_ROOT / "audit" / "norgate_membership_failures.csv"
        fail_path.parent.mkdir(exist_ok=True)
        pd.DataFrame(failures, columns=["symbol", "error"]).to_csv(fail_path, index=False)
        print(f"WARN: {len(failures)} symbols failed; wrote {fail_path}")

    return daily


def year_yaml_from_daily(year: int, daily: dict[pd.Timestamp, set[str]]) -> dict:
    jan1 = pd.Timestamp(f"{year}-01-01")
    year_end = pd.Timestamp(f"{year}-12-31")
    dates = sorted(d for d in daily if jan1 <= d <= year_end)
    if not dates:
        return {"year": year, "tickers_on_Jan_1": [], "changes": {}}

    jan_members = set(daily[dates[0]])
    changes = {}
    previous = jan_members
    for date in dates[1:]:
        current = set(daily[date])
        removed = sorted(previous - current)
        added = sorted(current - previous)
        if removed or added:
            changes[date.strftime("%Y-%m-%d")] = {
                "difference": removed,
                "union": added,
            }
        previous = current

    return {
        "year": year,
        "tickers_on_Jan_1": sorted(jan_members),
        "changes": changes,
    }


def write_yaml_files(index_key: str, daily: dict[pd.Timestamp, set[str]], start_year: int, end_year: int) -> None:
    cfg = INDEX_CONFIG[index_key]
    out_dir = REPO_ROOT / "src" / cfg["folder"]
    out_dir.mkdir(parents=True, exist_ok=True)

    for year in range(start_year, end_year + 1):
        data = year_yaml_from_daily(year, daily)
        path = out_dir / f"{cfg['file_prefix']}-{year}.yaml"
        with open(path, "w", encoding="utf-8") as fh:
            yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=False)
        print(f"wrote {path} ({len(data['tickers_on_Jan_1'])} Jan-1 members, {len(data['changes'])} change dates)")


def write_membership_parquet(index_key: str, daily: dict[pd.Timestamp, set[str]]) -> Path:
    out_dir = REPO_ROOT / "data"
    out_dir.mkdir(exist_ok=True)
    rows = [
        {
            "date": dt,
            "n_members": len(symbols),
            "tickers_json": json.dumps(sorted(symbols), separators=(",", ":")),
        }
        for dt, symbols in sorted(daily.items())
    ]
    path = out_dir / f"{index_key}_membership.parquet"
    pd.DataFrame(rows).to_parquet(path, index=False)
    print(f"wrote {path} ({len(rows)} daily snapshots)")
    return path


def publish_to_backtester(parquet_path: Path, backtester_data_dir: str) -> None:
    out_dir = Path(backtester_data_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / parquet_path.name
    shutil.copy2(parquet_path, target)
    print(f"published {target}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", default="Russell 2000", help="Russell 1000, Russell 2000, or Russell 3000")
    parser.add_argument("--start-date", default="2004-01-01")
    parser.add_argument("--end-date", default="2026-12-31")
    parser.add_argument("--candidate-database", action="append", default=[])
    parser.add_argument("--candidate-watchlist", action="append", default=[])
    parser.add_argument("--symbols-file", action="append", default=[])
    parser.add_argument("--parquet-data-dir", action="append", default=[])
    parser.add_argument("--progress-every", type=int, default=250)
    parser.add_argument("--skip-membership-parquet", action="store_true")
    parser.add_argument(
        "--backtester-data-dir",
        help="Optional july-backtester/data/holdings/legacy/data directory to receive the generated membership parquet.",
    )
    args = parser.parse_args()

    index_key = normalize_index(args.index)
    index_name = INDEX_CONFIG[index_key]["norgate_name"]
    symbols = candidate_symbols(args)
    print(f"Building {index_name} PIT from {len(symbols)} candidate symbols")

    daily = build_daily_membership(symbols, index_name, args.start_date, args.end_date, args.progress_every)
    if not daily:
        print("ERROR: no daily membership rows were produced.", file=sys.stderr)
        return 1

    write_yaml_files(index_key, daily, int(args.start_date[:4]), int(args.end_date[:4]))
    if not args.skip_membership_parquet:
        parquet_path = write_membership_parquet(index_key, daily)
        if args.backtester_data_dir:
            publish_to_backtester(parquet_path, args.backtester_data_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
