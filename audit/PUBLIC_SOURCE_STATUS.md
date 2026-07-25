# Public Russell PIT Source Status

## Collected Official Sources

The public collector has downloaded and parsed LSEG/FTSE Russell final Russell
3000 annual reconstitution additions/deletions PDFs for 2023-2026.

Extracted rows:

- 2023: 281 additions, 173 deletions
- 2024: 215 additions, 144 deletions
- 2025: 228 annual additions, 45 collected IPO additions, 151 deletions
- 2026: 224 annual additions, 11 collected IPO additions, 118 deletions

Files:

- `source_raw/lseg_russell_reconstitution/`
- `source_raw/github_gists/russell_3000_2011-06-27.csv`
- `source_raw/corporate_ir/russell3000_additions_2006.pdf`
- `source_raw/ftse_index_notices/`
- `source_raw/scribd_browser/`
- `audit/extracted_public_sources/source_manifest.csv`
- `audit/extracted_public_sources/ru3000_public_reconstitution_events.csv`
- `audit/extracted_public_sources/ftse_notice_ru3000_actions.csv`
- `audit/extracted_public_sources/membership_anchors/`
- `audit/public_source_leads.csv`
- `audit/missing_year_research_status.csv`

Additional collected anchor:

- 2010-06-28 Russell 3000 membership list from a browser-rendered Scribd copy of the Russell Investments list, extracted to 2,995 unique ticker rows.
- 2011-06-27 Russell 3000 ticker-only list from a GitHub gist, 2,975 nonblank rows.
- 2015-06-26 Russell 3000 membership list from Scribd JSONP page assets, extracted to 2,940 unique ticker rows.
- 2016-06-27 Russell 3000 membership PDF from an Elite Trader attachment, extracted to 2,991 unique ticker rows.
- 2017-06-26 Russell 3000 membership list from Scribd JSONP page assets, decoded from custom-font text to 2,975 unique ticker rows.
- 2018-06-25 Russell 3000 membership list from Scribd JSONP page assets, decoded from custom-font text to 2,964 unique ticker rows.
- 2019-07-01 Russell 3000 membership list from Scribd JSONP page assets, decoded from custom-font text to 2,950 unique ticker rows.
- 2020-06-29 Russell 3000 membership list from Scribd JSONP page assets, extracted to 3,011 unique ticker rows.
- 2021-06-28 Russell 3000 membership list from Scribd JSONP page assets, extracted to 3,011 unique ticker rows.
- 2022-06-24 Russell 3000 membership list from a browser-rendered Scribd copy of the FTSE Russell list, extracted to 3,010 unique ticker rows.
- 2014-06-27 Russell 2000 membership list from Scribd browser text, extracted to 1,973 unique ticker rows. This is useful for Russell 2000, not a Russell 3000 anchor.
- 2012-06-25 direct Russell 2000 membership list source found on Yumpu, but local HTML packs rows and extraction still needs cleanup.
- 2013-06-28 direct Russell 2000 membership list source found on Scribd; extraction still pending.
- 2018-06-25, 2019-07-01, 2021-06-28, and 2022-06-24 direct Russell 2000 membership list sources found on Scribd; local direct downloads hit Scribd client challenge and need browser/JSONP extraction.
- 2012-06-25 Russell 3000 Yumpu text is partially extracted to 2,207 rows but remains unvalidated because Yumpu removes row delimiters.
- 2006 Russell 3000 additions PDF mirrored on corporate-ir.net, extracted to 237 unique ticker rows.
- 2007 and 2008 NASDAQ issuer alerts, downloaded locally, confirming Russell preliminary additions/deletions dates and final membership-list posting dates for Russell 3000/Russell 2000. These are official schedule/context sources, not constituent lists.
- Manual Scribd bundle downloaded on 2026-07-25, including Russell 3000/Russell 2000 membership PDFs for 2010-2022, 2020/2021/2025 delta PDFs, and the previously blocked Northern Trust/ETF.com 2005 and 2007 reconstitution PDFs.
- Second manual Scribd batch downloaded on 2026-07-25 added cleaner Russell 3000 PDFs for 2011, 2015, and 2016. The 2011 second-batch parse produced 2,974 symbols and matches the existing 2011 gist except for one likely bad raw token. The 2015 second-batch parse produced 3,008 symbols and appears more complete than the earlier 2,940-symbol JSONP extraction. The 2016 second-batch parse produced 3,007 symbols but company names are partially shifted, so use it primarily as a symbol cross-check.
- Manual Scribd XLSX for 2018 Russell 2000 downloaded on 2026-07-25 and extracted cleanly to 2,021 unique symbols. This replaces the bad compressed-PDF parse for 2018 Russell 2000.
- 2004, 2005, 2007, 2008, and 2009 public research/news leads now logged for old reconstitution counts, posting dates, and single-company confirmations. No complete public old-year membership list has been collected from those leads yet.
- Eight official FTSE Russell index-notice PDFs for 2019-2022 context/corrections.
- 12 parsed Russell 3000 correction actions from official FTSE notices.

## Current Provisional Build

`scripts/build_provisional_from_public_deltas.py` generated Russell 3000 YAML
for 2023-2026 from:

- anchor: current/static `july-backtester/tickers_to_scan/russell-3000.json`
- official annual LSEG additions/deletions

This is useful as a scaffold, not as final PIT truth.

## Norgate Data Route

The repository has a Norgate-based PIT builder at
`scripts/build_from_norgate.py`. It uses `norgatedata.index_constituent_timeseries`,
which is the right source for true Russell historical membership. The local
`july-backtester-norgate-data` parquet export contains OHLCV/index/breadth bars
only, not historical constituent flags.

Diagnostic status:

- `norgatedata` Python package installed and importable.
- Norgate Data Updater was not reachable on 2026-07-24, so live constituent
  queries could not run yet.
- Added `scripts/diagnose_norgate_constituents.py` to recheck service access and
  print the Russell build commands once NDU is running.

## Known Gaps

Validation currently fails for 2004-2009 and 2012-2014 because no complete
public annual Russell 3000 sources have been collected for those years yet.
For 2006 specifically, public ticker data exists only as a Russell 3000 additions
file with 237 unique tickers, not as a full annual membership anchor.

Validation also reports 2023-2026 continuity mismatches. These are expected in a
delta-only build because the annual PDFs do not include every:

- daily deletion
- merger/acquisition removal
- ticker change
- quarterly IPO addition
- correction notice

## Next Collection Targets

1. Clean/validate the partial 2012 Yumpu extraction or find a cleaner 2012 source.
2. Find a true Russell 3000 2014 source; the collected 2014 Scribd source is Russell 2000.
3. Find missing 2013, 2014, 2016, 2017, and 2020-2022 official annual deltas.
4. Find missing LSEG quarterly IPO PDFs for 2023-2025 Q1/Q4/Q3 as applicable.
5. Evaluate `alemicheli/pyndex` as the research-grade reconstruction fallback for 2004-2019 if WRDS/CRSP access or equivalent security master data is available.
6. Search company PR/SEC filings for 2004-2009 membership mentions only as a last-resort supplemental source.
