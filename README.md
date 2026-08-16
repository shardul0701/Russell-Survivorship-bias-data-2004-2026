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
empty (0 files), not a placeholder file. For any year where both Russell 3000
and Russell 2000 rosters are genuine (non-fabricated), Russell 1000 membership
can be derived as `R3000 - R2000` for that year as a stopgap.

The 2026 file carries a full-year roster (3322 R3000 / 2007 R2000 names) even
though 2026 is not complete. Fine as a scaffold, but a consumer iterating
years should know this is a forward-looking universe for the current year,
not a closed historical one. Also note the `*-ticker-changes-YYYY.yaml`
filenames describe a delta-changes format, but the content is a roster
snapshot (`tickers_on_Jan_1` + `changes`) — don't assume the filename implies
a pure diff log.

## Read This Before Using — Corrected 2026-08-16

This repository currently contains a **public-source PIT scaffold**, not
perfect official/Norgate-grade Russell history. An external audit
([issue #68](https://github.com/zachisit/july-backtester-private-strategies/issues/68))
found the scaffold understated its own weaknesses. The findings below are
corrected against that audit and independently confirmed two ways: a
jaccard-similarity check across consecutive years, and an exhaustive
delisted-securities census against Norgate's parquet export (real
first/last-trade dates for ~36.7k securities).

**Do not use these years for backtesting.** Each block below is *one single
roster* stamped across multiple year-labels, not independent annual
snapshots:

| Index | Fabricated years | True single-sample anchor | Evidence |
| --- | --- | --- | --- |
| Russell 3000 | 2004-2011 (8 yrs, all byte-identical) | 2010 | census not-trading rate bottoms at 2010 (5.9%), rises to both sides |
| Russell 3000 | 2012-2015 (4 yrs, all byte-identical) | 2012 | census bottoms at 2012 (8.4%), rises through 2015 (19.0%) |
| Russell 2000 | 2004-2014 (11 yrs, all byte-identical) | 2013 | census bottoms at 2013 (5.8%) |
| Russell 2000 | 2015-2018 (4 yrs, all byte-identical) | 2015 | census bottoms at 2015 (8.2%) |
| Russell 2000 | 2020-2021 (2 yrs, byte-identical) | 2020 | census: 2020 6.8% vs 2021 10.5% |
| Russell 2000 | 2023-2026 (4 yrs, all byte-identical) | 2023 | census bottoms at 2023 (5.0%) |

That's roughly **half the dataset by year count** (8/23 R3000 years, 11/23
R2000 years the largest single culprits), concentrated in the older years —
which is exactly the range PIT data exists to get right.

**This is not just imprecision — it inverts the survivorship bias the
dataset exists to remove.** In the R3000 file labeled `2004`: `AVGO`, `VRSK`,
`RAX`, `SWI` are present despite not having IPO'd until 2008-2009, while
`LEH`, `BSC`, `MER`, `WB`, `CFC`, `NCC`, `CC` — the 2008-09 financial-crisis
casualty list — are absent despite unquestionably being Russell 3000 members
on 2004-01-01. A backtest run against the uncorrected 2004-2011 files buys
companies years before they listed and can never hold the names that failed —
the exact error this dataset exists to prevent.

Every YAML file includes a `metadata` block with its confidence/status.
Years within the blocks above are now labeled `fabricated_identical_roster_duplicate`
where they previously falsely claimed independent-anchor status, and every
year inside an identical-roster block (regardless of label) carries an
explicit "FABRICATED — DO NOT USE FOR BACKTESTING" warning naming the full
block range. `scripts/validate_yaml.py` fails any file that is
byte-identical (jaccard = 1.0) to its predecessor without an honest
copy-of-a-prior-year label, so this class of error cannot silently recur.
Files still marked `backfilled_scaffold_*`, `carried_forward_no_direct_public_anchor`,
or `public_delta_derived_from_prior_anchor` outside an identical-roster block
remain best-effort placeholders — usable with caution, not fabricated.

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
