#!/usr/bin/env python3
"""
Delisted-securities census for point-in-time (PIT) index rosters.

WHAT IT ANSWERS
---------------
For every roster year Y in a PIT dataset, of the N tickers claimed to be members
on Jan 1 of year Y, how many were *actually trading* during Y?

A roster built by copying a later year's membership backwards will contain names
that had not listed yet, and will be missing the names that died. This script
measures the first of those two errors directly. It cannot measure the second
(members wrongly omitted) -- that is the survivorship half, and it is strictly
worse, because the omissions are not random: they are the companies that failed.

WHY IT WORKS
------------
A Norgate parquet export keeps delisted securities under a
``TICKER-YYYYMM`` naming convention (``BSC-200805``, ``CFC-200806``,
``MER-200812``), so real first/last trade dates survive for securities that no
longer exist. That is what makes "was this name trading in 2004?" answerable at
all -- a live-universe price feed cannot answer it.

HOW TO READ THE OUTPUT
----------------------
The not-trading rate never reaches 0% even for a genuine roster: symbology
mismatches, dual-class tickers (``BH.A``), and names simply absent from the
export put a floor of roughly 5-6% under it. **Real contamination is the excess
over that floor, not the raw rate.**

The diagnostic that identifies a fabricated block is the *shape*: across a run of
years sharing one copied roster, the not-trading rate traces a V whose minimum
lands on the year the roster was actually sampled. Error is smallest at the true
anchor and grows monotonically the further it is extrapolated in either
direction. Use ``--summary`` to print each block's argmin.

Tickers with no file at all are reported as ``unresolved`` and are NOT counted
against the roster: absence from the export is not proof of non-existence.

USAGE
-----
    python scripts/census_delisted_coverage.py \
        --norgate /path/to/parquet_data/data \
        --src src/russell_3000_ticker_history src/russell_2000_ticker_history \
        --out audit/delisted_census.csv --summary

Generalises to any PIT roster directory whose YAML files carry a
``tickers_on_Jan_1`` list and a 4-digit year in the filename -- the S&P 500 and
NQ100 PIT repos included.

Requires: pandas, pyarrow, pyyaml.
"""

from __future__ import annotations

import argparse
import csv
import glob
import os
import re
import sys
from collections import defaultdict

import pandas as pd
import pyarrow.parquet as pq
import yaml

# A delisted security is stored as TICKER-YYYYMM; strip that to get the ticker.
_DELISTED_SUFFIX = re.compile(r"-\d{6}$")
_YEAR_IN_NAME = re.compile(r"(\d{4})")


def build_index(norgate_dir: str) -> dict[str, list[str]]:
    """Map bare ticker -> every parquet that could be that ticker.

    A ticker may resolve to several files: the live security plus one entry per
    delisting. `V` is Visa today and was Vivendi before 2008; `OPEN` predates
    Opendoor. Collapsing them into one bare key and treating the ticker as alive
    if ANY candidate traded in the year is the conservative choice -- it can only
    *understate* contamination, never invent it.
    """
    idx: dict[str, list[str]] = defaultdict(list)
    paths = glob.glob(os.path.join(norgate_dir, "*.parquet"))
    if not paths:
        sys.exit(f"[FATAL] no parquet files under {norgate_dir!r}")
    for p in paths:
        stem = os.path.basename(p)[: -len(".parquet")]
        idx[_DELISTED_SUFFIX.sub("", stem)].append(p)
    return dict(idx)


_span_cache: dict[str, tuple[pd.Timestamp, pd.Timestamp] | None] = {}


def trading_span(path: str) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    """First and last bar timestamp, read from row-group statistics only.

    THE ONE NON-OBVIOUS BIT: ``Datetime`` is *not* column 0 in these files --
    that is ``Open``. Locating the column by position instead of by name yields
    1970 epoch timestamps and a silent 100% failure rate, where every ticker
    looks dead in every year. Always resolve by ``path_in_schema``.

    Reading statistics rather than the data keeps this at metadata cost, which is
    what makes a ~37k-file corpus feasible to sweep.
    """
    if path in _span_cache:
        return _span_cache[path]
    try:
        md = pq.ParquetFile(path).metadata
        rg0 = md.row_group(0)
        col = next(
            i
            for i in range(rg0.num_columns)
            if rg0.column(i).path_in_schema == "Datetime"
        )
        lo = min(
            md.row_group(g).column(col).statistics.min for g in range(md.num_row_groups)
        )
        hi = max(
            md.row_group(g).column(col).statistics.max for g in range(md.num_row_groups)
        )
        span = (
            pd.Timestamp(lo).tz_localize(None),
            pd.Timestamp(hi).tz_localize(None),
        )
    except Exception:  # unreadable/empty file -> treat as no evidence
        span = None
    _span_cache[path] = span
    return span


def status(ticker: str, year: int, idx: dict[str, list[str]]) -> str:
    """'yes' | 'no' | 'unresolved' -- did any security with this ticker trade in `year`?"""
    paths = idx.get(ticker)
    if not paths:
        return "unresolved"
    y0 = pd.Timestamp(f"{year}-01-01")
    y1 = pd.Timestamp(f"{year}-12-31")
    seen = False
    for p in paths:
        span = trading_span(p)
        if span is None:
            continue
        seen = True
        if span[0] <= y1 and span[1] >= y0:
            return "yes"
    return "no" if seen else "unresolved"


def load_rosters(src_dir: str) -> dict[int, list[str]]:
    """year -> membership list, from every YAML in a roster directory."""
    out: dict[int, list[str]] = {}
    for f in sorted(glob.glob(os.path.join(src_dir, "*.yaml"))):
        years = _YEAR_IN_NAME.findall(os.path.basename(f))
        if not years:
            continue
        # filenames embed the index too (russell_3000_2004.yaml) -- the year is last.
        doc = yaml.safe_load(open(f)) or {}
        out[int(years[-1])] = list(doc.get("tickers_on_Jan_1") or [])
    return dict(sorted(out.items()))


def census(src_dir: str, idx: dict[str, list[str]]) -> list[dict]:
    rows = []
    for year, tickers in load_rosters(src_dir).items():
        counts = {"yes": 0, "no": 0, "unresolved": 0}
        for t in tickers:
            counts[status(t, year, idx)] += 1
        judged = counts["yes"] + counts["no"]
        rows.append(
            {
                "roster": os.path.basename(src_dir.rstrip("/")),
                "year": year,
                "members": len(tickers),
                "alive": counts["yes"],
                "not_trading": counts["no"],
                "unresolved": counts["unresolved"],
                "not_trading_pct": round(100 * counts["no"] / judged, 1) if judged else "",
            }
        )
    return rows


def identical_blocks(src_dir: str) -> list[tuple[int, int]]:
    """Runs of consecutive years whose rosters are byte-identical (jaccard == 1.0)."""
    rosters = {y: set(t) for y, t in load_rosters(src_dir).items()}
    years = sorted(rosters)
    blocks, start = [], None
    for a, b in zip(years, years[1:]):
        same = rosters[a] and rosters[a] == rosters[b]
        if same and start is None:
            start = a
        elif not same and start is not None:
            blocks.append((start, a))
            start = None
    if start is not None:
        blocks.append((start, years[-1]))
    return blocks


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--norgate", required=True, help="directory of Norgate parquet exports")
    ap.add_argument("--src", nargs="+", required=True, help="one or more PIT roster directories")
    ap.add_argument("--out", help="write results to this CSV")
    ap.add_argument("--summary", action="store_true", help="also print identical-roster blocks and their argmin year")
    args = ap.parse_args()

    idx = build_index(args.norgate)
    print(f"indexed {len(idx)} distinct tickers from {args.norgate}", file=sys.stderr)

    all_rows: list[dict] = []
    for src in args.src:
        rows = census(src, idx)
        all_rows += rows
        name = os.path.basename(src.rstrip("/"))
        print(f"\n{name}")
        print(f"{'year':>6} {'n':>6} {'alive':>7} {'not trading':>12} {'%':>7} {'unresolved':>11}")
        for r in rows:
            print(f"{r['year']:>6} {r['members']:>6} {r['alive']:>7} {r['not_trading']:>12} "
                  f"{r['not_trading_pct']:>6}% {r['unresolved']:>11}")

        if args.summary:
            blocks = identical_blocks(src)
            if blocks:
                by_year = {r["year"]: r for r in rows}
                print(f"\n  identical-roster blocks (jaccard == 1.000):")
                for lo, hi in blocks:
                    span = [by_year[y] for y in range(lo, hi + 1) if y in by_year]
                    best = min(span, key=lambda r: r["not_trading_pct"] or 999)
                    print(f"    {lo}-{hi} ({hi - lo + 1} yrs) -> census minimum at "
                          f"{best['year']} ({best['not_trading_pct']}%), the inferred true anchor")
            else:
                print("\n  no identical-roster blocks found")

    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(all_rows[0].keys()))
            w.writeheader()
            w.writerows(all_rows)
        print(f"\nwrote {len(all_rows)} rows -> {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
