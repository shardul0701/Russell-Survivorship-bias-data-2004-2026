# Russell-Survivorship-bias-data-2004-2026

Point-in-time Russell constituent data generator in the same YAML style as the
S&P 500 and Nasdaq-100 PIT repos.

## What This Is

This repo is intended to hold Russell 1000, Russell 2000, and Russell 3000
membership history from 2004 to 2026.

Each generated year file records:

- the exact members on January 1 of that year
- every date in the year where membership changed

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

Generated from Norgate Data historical index constituent time series. Norgate's
Python docs describe `index_constituent_timeseries(symbol, indexname)` for this
purpose and note that historical index constituents require the appropriate
Stocks subscription tier.

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
