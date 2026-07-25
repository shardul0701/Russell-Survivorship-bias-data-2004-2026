# Russell-Survivorship-bias-data-2004-2026

Point-in-time Russell constituent data generator in the same YAML style as the
S&P 500 and Nasdaq-100 PIT repos.

## Where The YAML Files Are

The generated PIT YAML files live under `src/`:

- Russell 3000: `src/russell_3000_ticker_history/russell-3000-ticker-changes-YYYY.yaml`
- Russell 2000: `src/russell_2000_ticker_history/russell-2000-ticker-changes-YYYY.yaml`

There are 46 generated YAML files total:

- 23 Russell 3000 files, 2004-2026
- 23 Russell 2000 files, 2004-2026

Russell 1000 is not built yet; `src/russell_1000_ticker_history/` is currently
only a placeholder.

## Read This Before Using

This repository currently contains a **public-source PIT scaffold**, not
perfect official/Norgate-grade Russell history.

The file format is correct and the generated universes are usable by a
backtester, but users should be aware of source uncertainty:

- 2004-2009 are the weakest years. No complete public Russell 2000/Russell 3000
  membership list has been collected for those years yet.
- Russell 3000 files for 2004-2009 are backfilled from the 2010 public
  membership anchor, so they are structural placeholders, not true historical
  2004-2009 rosters.
- Russell 2000 files for 2004-2012 are backfilled from the 2013 public
  membership anchor, so they are also placeholders for those years.
- Russell 3000 files for 2012-2014 carry the 2011 roster until the 2015 anchor
  because full clean Russell 3000 anchors for those years are still missing.
- Russell 2000 files for 2015-2017 carry the 2014 roster until the 2018 anchor.
- Russell 2000 file for 2020 carries the 2019 roster until the 2021 anchor.
- Russell 2000 files for 2023-2026 carry the 2022 roster because no Russell
  2000 public delta files were collected.
- Russell 3000 files for 2023-2026 use public additions/deletions deltas, but
  annual deltas may miss interim removals, acquisitions, ticker changes,
  correction notices, and some IPO/quarterly changes.

Every YAML file includes a `metadata` block with its confidence/status. Treat
files marked `backfilled_scaffold_*`, `carried_forward_no_direct_public_anchor`,
or `public_delta_derived_from_prior_anchor` with caution.

## What This Is

This repo is intended to hold Russell 1000, Russell 2000, and Russell 3000
membership history from 2004 to 2026.

Each generated year file is intended to record:

- members on January 1 of that year
- dated membership changes where collected sources allow them

Static Russell JSON files are not used because they are current-member lists and
are survivorship-biased.

## Build From Norgate

Norgate's exported OHLCV parquet files are not enough to recover historical
membership. The generator uses the Norgate Python API's historical index
constituent time series.

Requirements:

- `pip install norgatedata pyyaml pandas`
- Norgate Data Updater running on Windows
- Norgate Stocks subscription tier with historical index constituents

Example:

```bash
python scripts/build_from_norgate.py --index "Russell 2000" --start-date 2004-01-01 --end-date 2026-12-31 --parquet-data-dir "C:\Users\shard\Light Water Internship\july-backtester-norgate-data\data" --backtester-data-dir "C:\Users\shard\Light Water Internship\New folder\july-backtester\data\holdings\legacy\data"
python scripts/validate_yaml.py --index russell2000
python scripts/build_universe.py --index russell2000 2015-06-01
```

For a candidate scan directly from Norgate, use both active and delisted
databases:

```bash
python scripts/build_from_norgate.py --index "Russell 2000" --candidate-database "US Equities" --candidate-database "US Equities Delisted"
```

The `--parquet-data-dir` option only uses file names as the candidate symbol
pool; membership still comes from `index_constituent_timeseries`.

## YAML Format

```yaml
year: 2010

tickers_on_Jan_1:
  - ABC
  - XYZ

changes:
  '2010-06-28':
    difference:
      - OLD
    union:
      - NEW
```

## Source

The committed YAML files are generated from collected public membership anchors,
manual Scribd downloads, extracted public CSVs, and official/public FTSE Russell
additions/deletions where available.

The repo also includes a Norgate builder. If historical Norgate constituent
access is available, `scripts/build_from_norgate.py` should produce stronger
true PIT history than the current public scaffold.

## Public-Source Reconstruction

We also started a public-source reconstruction path for cases where Norgate
constituent access is not available.

Collected so far:

- official LSEG/FTSE Russell final Russell 3000 additions/deletions PDFs for
  2023, 2024, 2025, and 2026
- extracted normalized event CSV:
  `audit/extracted_public_sources/ru3000_public_reconstitution_events.csv`
- raw PDFs and text extraction under:
  `source_raw/lseg_russell_reconstitution/`

Run:

```bash
python scripts/collect_public_sources.py
python scripts/build_provisional_from_public_deltas.py --anchor-file "C:\Users\shard\Light Water Internship\New folder\july-backtester\tickers_to_scan\russell-3000.json" --anchor-year 2026 --anchor-date 2026-06-29
```

Important: this output is provisional. Annual additions/deletions do not capture
all daily deletions, ticker changes, acquisitions, or quarterly IPO additions.
The validation gaps are useful audit targets, not noise.

The current public-anchor PIT scaffold can be rebuilt with:

```bash
python scripts/parse_manual_scribd_bundle.py
python scripts/build_pit_from_public_anchors.py
python scripts/validate_yaml.py --index russell3000
python scripts/validate_yaml.py --index russell2000
```

Status and source-quality notes are tracked in:

- `audit/PIT_BUILD_STATUS.md`
- `audit/public_anchor_pit_build_report.csv`

Next source targets:

- LSEG quarterly IPO addition PDFs for 2023-2026
- LSEG preliminary/update PDFs for May/June 2023-2026, to capture corrections
- older LSEG/FTSE Russell reconstitution PDFs for 2020-2022
- archived FTSE Russell pages/Wayback snapshots for 2004-2019
- ETF holdings history only as a secondary cross-check, not as primary index truth
