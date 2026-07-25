# Russell PIT YAML Build Status

Generated on 2026-07-25 from collected public anchors and deltas using:

`python scripts/build_pit_from_public_anchors.py`

## Outputs

- Russell 3000 YAML: `src/russell_3000_ticker_history/russell-3000-ticker-changes-YYYY.yaml`
- Russell 2000 YAML: `src/russell_2000_ticker_history/russell-2000-ticker-changes-YYYY.yaml`
- Build report: `audit/public_anchor_pit_build_report.csv`
- Build log: `audit/last_public_anchor_pit_build.log`

Each YAML file follows the S&P/NQ-style schema:

```yaml
year: 2025
tickers_on_Jan_1:
  - AAPL
changes:
  '2025-06-30':
    difference:
      - OLD
    union:
      - NEW
```

## Russell 3000 Coverage

Direct public membership anchors:

- 2010, 2011
- 2015, 2016, 2017, 2018, 2019
- 2020, 2021, 2022

Delta-derived years:

- 2023, 2024, 2025, 2026 from official/public Russell 3000 additions and deletions CSVs.

Scaffolded/carry years:

- 2004-2009 are backfilled from the 2010 anchor because no full public old-year membership list has been collected.
- 2012-2014 carry the 2011 roster until the 2015 anchor.

## Russell 2000 Coverage

Direct public membership anchors:

- 2013, 2014
- 2018, 2019
- 2021, 2022

Scaffolded/carry years:

- 2004-2012 are backfilled from the 2013 anchor.
- 2015-2017 carry the 2014 roster until the 2018 anchor.
- 2020 carries the 2019 roster until the 2021 anchor.
- 2023-2026 carry the 2022 roster because no Russell 2000 public deltas were collected.

## Validation

Both generated indexes pass the repo validator:

```bash
python scripts/validate_yaml.py --index russell3000
python scripts/validate_yaml.py --index russell2000
```

Spot lookup checks also pass:

```bash
python scripts/build_universe.py --index russell3000 2025-07-01
python scripts/build_universe.py --index russell2000 2018-06-25
```

## Important Caveat

This is a public-source PIT scaffold, not Norgate-grade truth. The YAML files
are shaped correctly and usable by the backtester, but years marked
`backfilled_scaffold_*`, `carried_forward_no_direct_public_anchor`, or
`public_delta_derived_from_prior_anchor` are not complete true historical
membership unless better sources are added later.

