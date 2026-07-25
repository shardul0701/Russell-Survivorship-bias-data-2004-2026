"""Build provisional Russell 3000 YAML from public reconstitution deltas.

This requires an anchor membership list. The public PDFs collected by
collect_public_sources.py are mostly additions/deletions, so they can move an
anchor backward/forward but cannot create an absolute roster from nothing.

Output is intentionally marked provisional in audit metadata.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
EVENTS_CSV = REPO_ROOT / "audit" / "extracted_public_sources" / "ru3000_public_reconstitution_events.csv"
OUT_DIR = REPO_ROOT / "src" / "russell_3000_ticker_history"
AUDIT_DIR = REPO_ROOT / "audit"


def clean_symbols(symbols: list[object]) -> list[str]:
    return sorted({str(s).strip().upper() for s in symbols if str(s).strip()})


def load_anchor(path: Path) -> list[str]:
    if path.suffix.lower() == ".json":
        return clean_symbols(json.loads(path.read_text(encoding="utf-8")))
    if path.suffix.lower() in {".csv", ".txt"}:
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.lower().startswith("symbol"):
                continue
            rows.append(line.split(",")[0].strip())
        return clean_symbols(rows)
    raise ValueError(f"Unsupported anchor file type: {path}")


def grouped_events() -> dict[int, dict[str, set[str]]]:
    df = pd.read_csv(EVENTS_CSV)
    df = df[df["stage"].astype(str).str.startswith("final")]
    events: dict[int, dict[str, set[str]]] = {}
    for (year, action), group in df.groupby(["year", "action"]):
        events.setdefault(int(year), {"additions": set(), "deletions": set()})
        key = "deletions" if str(action) == "deletions" else "additions"
        events[int(year)][key].update(clean_symbols(group["symbol"].tolist()))
    return events


def reverse_to_year_starts(anchor_symbols: set[str], anchor_year: int, events: dict[int, dict[str, set[str]]]) -> dict[int, set[str]]:
    starts: dict[int, set[str]] = {}
    current = set(anchor_symbols)
    for year in range(anchor_year, 2022, -1):
        starts[year + 1] = set(current)
        additions = events.get(year, {}).get("additions", set())
        deletions = events.get(year, {}).get("deletions", set())
        current = (current - additions) | deletions
    starts[2023] = set(current)
    return starts


def write_years(starts: dict[int, set[str]], events: dict[int, dict[str, set[str]]], effective_dates: dict[int, str]) -> None:
    df = pd.read_csv(EVENTS_CSV)
    df = df[df["stage"].astype(str).str.startswith("final")]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for year in sorted(starts):
        if year > 2026:
            continue
        changes = {}
        year_df = df[df["year"].eq(year)]
        for effective_date, date_group in year_df.groupby("effective_date"):
            additions = set()
            deletions = set()
            for action, action_group in date_group.groupby("action"):
                symbols = set(clean_symbols(action_group["symbol"].tolist()))
                if str(action) == "deletions":
                    deletions.update(symbols)
                else:
                    additions.update(symbols)
            if additions or deletions:
                changes[str(effective_date)] = {
                    "difference": sorted(deletions),
                    "union": sorted(additions),
                }
        additions_count = len(events.get(year, {}).get("additions", set()))
        deletions_count = len(events.get(year, {}).get("deletions", set()))
        data = {
            "year": year,
            "tickers_on_Jan_1": sorted(starts[year]),
            "changes": changes,
            "metadata": {
                "confidence": "provisional_public_delta_from_anchor",
                "source": "LSEG/FTSE Russell final Russell 3000 additions/deletions/IPO PDFs plus external anchor",
            },
        }
        path = OUT_DIR / f"russell-3000-ticker-changes-{year}.yaml"
        with open(path, "w", encoding="utf-8") as fh:
            yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=False)
        print(f"wrote {path}: {len(starts[year])} Jan-1 members, {additions_count} adds, {deletions_count} deletes")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anchor-file", required=True, help="Current/post-reconstitution Russell 3000 symbol list")
    parser.add_argument("--anchor-year", type=int, default=2026, help="Year of the latest public delta already reflected in the anchor")
    parser.add_argument("--anchor-date", default="2026-06-29")
    args = parser.parse_args()

    if not EVENTS_CSV.exists():
        raise FileNotFoundError(f"Run collect_public_sources.py first: {EVENTS_CSV}")

    anchor = set(load_anchor(Path(args.anchor_file)))
    events = grouped_events()
    effective_dates = {
        int(row["year"]): str(row["effective_date"])
        for _, row in pd.read_csv(EVENTS_CSV).drop_duplicates("year").iterrows()
    }
    starts = reverse_to_year_starts(anchor, args.anchor_year, events)
    write_years(starts, events, effective_dates)

    AUDIT_DIR.mkdir(exist_ok=True)
    report = {
        "anchor_file": args.anchor_file,
        "anchor_date": args.anchor_date,
        "anchor_symbols": len(anchor),
        "years_built": sorted(y for y in starts if y <= 2026),
        "warning": "Provisional only. Collected public deltas still do not include every daily deletion, ticker change, correction notice, or missing quarter.",
    }
    (AUDIT_DIR / "public_delta_provisional_build.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
