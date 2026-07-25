"""Point-in-time Russell universe lookup from generated YAML files."""

from __future__ import annotations

import argparse
from functools import lru_cache
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
INDEXES = {
    "russell1000": ("russell_1000_ticker_history", "russell-1000-ticker-changes"),
    "russell2000": ("russell_2000_ticker_history", "russell-2000-ticker-changes"),
    "russell3000": ("russell_3000_ticker_history", "russell-3000-ticker-changes"),
}


def normalize_index(index: str) -> str:
    key = index.strip().lower().replace("-", "").replace("_", "").replace(" ", "")
    aliases = {
        "rut": "russell2000",
        "rty": "russell2000",
        "rui": "russell1000",
        "rua": "russell3000",
    }
    return aliases.get(key, key)


@lru_cache(maxsize=None)
def load_year(index: str, year: int) -> dict:
    folder, prefix = INDEXES[index]
    path = REPO_ROOT / "src" / folder / f"{prefix}-{year}.yaml"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def get_universe_as_of(date_str: str, index: str = "russell2000") -> list[str]:
    index = normalize_index(index)
    if index not in INDEXES:
        raise ValueError(f"Unsupported index {index!r}")
    year = int(date_str[:4])
    data = load_year(index, year)
    current = set(data.get("tickers_on_Jan_1", []))
    for change_date, entry in sorted((data.get("changes") or {}).items()):
        if change_date > date_str:
            break
        current -= set(entry.get("difference", []))
        current |= set(entry.get("union", []))
    return sorted(current)


def get_all_historical_tickers(index: str = "russell2000") -> set[str]:
    index = normalize_index(index)
    all_tickers: set[str] = set()
    for year in range(2004, 2027):
        data = load_year(index, year)
        all_tickers.update(data.get("tickers_on_Jan_1", []))
        for entry in (data.get("changes") or {}).values():
            all_tickers.update(entry.get("difference", []))
            all_tickers.update(entry.get("union", []))
    return all_tickers


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("date", nargs="?")
    parser.add_argument("--index", default="russell2000")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    if args.all:
        tickers = sorted(get_all_historical_tickers(args.index))
        print(f"{args.index} all historical tickers: {len(tickers)}")
        print(", ".join(tickers[:30]) + (" ..." if len(tickers) > 30 else ""))
        return 0
    if not args.date:
        parser.error("provide YYYY-MM-DD or --all")

    tickers = get_universe_as_of(args.date, args.index)
    print(f"{args.index} as of {args.date}: {len(tickers)} tickers")
    print(", ".join(tickers[:30]) + (" ..." if len(tickers) > 30 else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
