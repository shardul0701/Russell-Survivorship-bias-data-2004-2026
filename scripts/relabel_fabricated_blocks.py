#!/usr/bin/env python3
"""
Regenerate the confidence label for every year inside a fabricated
identical-roster block, per issue #68.

Each block gets exactly one honest label at its census-inferred anchor year
(``anchor_inferred_from_delisted_census``); every other year in the block is
labeled a duplicate naming the specific year it was copied from
(``fabricated_identical_roster_duplicate_of_<anchor-year>``). Previously every
year in a block carried the same verdict, discarding the real distinction
between the one genuinely-sampled roster and its copies.

The anchor is inferred evidence, not proven provenance -- the census
not-trading floor is roughly 5-6% noise and the argmin is a heuristic over
that noise (a strong one: the V-shape is unambiguous). The label name and the
generated warning text both say "inferred", not "anchor" alone, so a reader
never mistakes this for a provenance claim the data can't support.

Block boundaries come from ``identical_blocks()`` in
``census_delisted_coverage.py`` -- pure roster-to-roster comparison, no
Norgate access needed. The anchor year comes from the already-committed
``audit/delisted_census.csv``, so this labeling step needs no live Norgate
export, only whatever census was last generated. Re-run this after
``census_delisted_coverage.py`` regenerates that CSV to keep labels in sync;
that is what makes labels a build step instead of something hand-maintained
that can drift.

Usage:
    python scripts/relabel_fabricated_blocks.py
    python scripts/relabel_fabricated_blocks.py --dry-run
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from census_delisted_coverage import identical_blocks  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]

ANCHOR_LABEL = "anchor_inferred_from_delisted_census"


class _IndentedDumper(yaml.SafeDumper):
    """Indent block-sequence items under their parent key (matches the
    existing YAML files' style, e.g. ``tickers_on_Jan_1:\n  - A``).
    PyYAML's default dump is indentless here and would rewrite every
    unrelated line in the file, burying the actual metadata change in a
    multi-thousand-line diff."""

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


def load_census(csv_path: Path) -> dict[tuple[str, int], float]:
    """(roster, year) -> not_trading_pct, from the committed census CSV."""
    out: dict[tuple[str, int], float] = {}
    with open(csv_path, newline="") as fh:
        for row in csv.DictReader(fh):
            pct = row["not_trading_pct"]
            if pct == "":
                continue
            out[(row["roster"], int(row["year"]))] = float(pct)
    return out


def relabel_file(
    path: Path,
    is_anchor: bool,
    anchor_year: int,
    lo: int,
    hi: int,
    pct: float,
    dry_run: bool,
) -> None:
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    meta = data.setdefault("metadata", {})
    old_conf = meta.get("confidence")
    span = hi - lo + 1

    if is_anchor:
        meta["confidence"] = ANCHOR_LABEL
        meta["warning"] = (
            f"FABRICATED-BLOCK ANCHOR (INFERRED, NOT PROVEN) -- this roster is "
            f"stamped across {lo}-{hi} ({span} consecutive year-labels), and this "
            f"year has the lowest not-trading rate in that range's "
            f"delisted-securities census ({pct}%), inferred to be the year the "
            f"roster was actually sampled. This is evidence, not proof -- the "
            f"census floor is roughly 5-6% noise and the argmin is a heuristic "
            f"over that noise. Still unusable as a multi-year series: this is a "
            f"single Jan-1 snapshot copied across {span} years, and every other "
            f"year in this range is a confirmed duplicate of it. See issue #68 "
            f"for the full audit (zachisit/july-backtester-private-strategies#68)."
        )
    else:
        meta["confidence"] = f"fabricated_identical_roster_duplicate_of_{anchor_year}"
        meta["warning"] = (
            f"FABRICATED -- DO NOT USE FOR BACKTESTING. This roster is "
            f"byte-identical (jaccard=1.0) across all of {lo}-{hi} ({span} "
            f"consecutive year-labels). The delisted-securities census points to "
            f"{anchor_year} as the inferred true anchor ({pct}%, the range "
            f"minimum); this year is a copy of that {anchor_year} roster "
            f"stamped under a different year-label. See issue #68 for the full "
            f"audit (zachisit/july-backtester-private-strategies#68)."
        )

    print(f"{'DRY ' if dry_run else ''}{path.name}: {old_conf} -> {meta['confidence']}")
    if dry_run:
        return
    with open(path, "w", encoding="utf-8") as fh:
        yaml.dump(data, fh, Dumper=_IndentedDumper, sort_keys=False, allow_unicode=False, default_flow_style=False)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--src",
        nargs="+",
        default=[
            str(REPO_ROOT / "src" / "russell_3000_ticker_history"),
            str(REPO_ROOT / "src" / "russell_2000_ticker_history"),
        ],
    )
    ap.add_argument("--census", default=str(REPO_ROOT / "audit" / "delisted_census.csv"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    census = load_census(Path(args.census))

    for src in args.src:
        src_path = Path(src)
        roster_name = src_path.name
        blocks = identical_blocks(str(src_path))
        if not blocks:
            print(f"{roster_name}: no identical-roster blocks found")
            continue
        for lo, hi in blocks:
            years_in_census = {
                y: census[(roster_name, y)]
                for y in range(lo, hi + 1)
                if (roster_name, y) in census
            }
            if not years_in_census:
                print(f"WARN {roster_name} {lo}-{hi}: no census data, skipping", file=sys.stderr)
                continue
            anchor_year = min(years_in_census, key=lambda y: years_in_census[y])
            anchor_pct = years_in_census[anchor_year]
            print(f"\n{roster_name} block {lo}-{hi} -> anchor {anchor_year} ({anchor_pct}%)")
            for year in range(lo, hi + 1):
                matches = list(src_path.glob(f"*-{year}.yaml"))
                if not matches:
                    print(f"WARN {roster_name} {year}: no YAML file, skipping", file=sys.stderr)
                    continue
                relabel_file(matches[0], year == anchor_year, anchor_year, lo, hi, anchor_pct, args.dry_run)

    return 0


if __name__ == "__main__":
    sys.exit(main())
