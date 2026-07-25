"""Build Russell PIT YAML from collected public membership anchors.

The output intentionally matches the S&P/NQ year-by-year YAML shape:

    year: 2025
    tickers_on_Jan_1:
      - AAPL
    changes:
      "2025-06-30":
        difference:
          - OLD
        union:
          - NEW

For years without a direct public membership anchor, the script carries the
nearest known roster forward/backward and labels the year in metadata. This
keeps the backtester interface stable while making evidence quality explicit.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
ANCHOR_DIR = REPO_ROOT / "audit" / "extracted_public_sources" / "membership_anchors"
EVENTS_CSV = REPO_ROOT / "audit" / "extracted_public_sources" / "ru3000_public_reconstitution_events.csv"
OUT_SRC = REPO_ROOT / "src"
AUDIT_DIR = REPO_ROOT / "audit"


class IndentDumper(yaml.SafeDumper):
    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


@dataclass(frozen=True)
class Anchor:
    year: int
    as_of: str
    path: Path
    source: str
    confidence: str = "public_membership_anchor"


INDEXES = {
    "russell3000": {
        "folder": "russell_3000_ticker_history",
        "prefix": "russell-3000-ticker-changes",
        "min_members": 2400,
        "max_members": 3600,
        "anchors": [
            Anchor(2010, "2010-06-28", ANCHOR_DIR / "russell3000_2010-06-28_scribd_manual_pdf.csv", "Scribd manual PDF extraction of Russell Investments 2010 list"),
            Anchor(2011, "2011-06-27", ANCHOR_DIR / "russell3000_2011-06-27_scribd_second_batch_pdf.csv", "Scribd second-batch PDF extraction of Russell Investments 2011 list"),
            Anchor(2015, "2015-06-26", ANCHOR_DIR / "russell3000_2015-06-26_scribd_second_batch_pdf.csv", "Scribd second-batch PDF extraction of Russell 3000 2015 list"),
            Anchor(2016, "2016-06-27", ANCHOR_DIR / "russell3000_2016-06-27_scribd_second_batch_pdf_symbol_check.csv", "Scribd second-batch 2016 symbol extraction; company names partially shifted"),
            Anchor(2017, "2017-06-26", ANCHOR_DIR / "russell3000_2017-06-26_scribd_decoded.csv", "Scribd decoded custom-font extraction of Russell 3000 2017 list"),
            Anchor(2018, "2018-06-25", ANCHOR_DIR / "russell3000_2018-06-25_scribd_decoded.csv", "Scribd decoded custom-font extraction of Russell 3000 2018 list"),
            Anchor(2019, "2019-07-01", ANCHOR_DIR / "russell3000_2019-07-01_scribd_manual_pdf.csv", "Scribd manual PDF extraction of Russell 3000 2019 list"),
            Anchor(2020, "2020-06-29", ANCHOR_DIR / "russell3000_2020-06-29_scribd_jsonp.csv", "Scribd JSONP extraction of Russell 3000 2020 list"),
            Anchor(2021, "2021-06-28", ANCHOR_DIR / "russell3000_2021-06-28_scribd_jsonp.csv", "Scribd JSONP extraction of Russell 3000 2021 list"),
            Anchor(2022, "2022-06-24", ANCHOR_DIR / "russell3000_2022-06-24_scribd_browser.csv", "Browser-rendered Scribd extraction of FTSE Russell 2022 list"),
        ],
        "use_public_ru3000_deltas_after": 2022,
    },
    "russell2000": {
        "folder": "russell_2000_ticker_history",
        "prefix": "russell-2000-ticker-changes",
        "min_members": 1500,
        "max_members": 2300,
        "anchors": [
            Anchor(2013, "2013-06-28", ANCHOR_DIR / "russell2000_2013-06-28_scribd_manual_pdf.csv", "Scribd manual PDF extraction of Russell 2000 2013 list"),
            Anchor(2014, "2014-06-27", ANCHOR_DIR / "russell2000_2014-06-27_scribd_manual_pdf.csv", "Scribd manual PDF extraction of Russell 2000 2014 list"),
            Anchor(2018, "2018-06-25", ANCHOR_DIR / "russell2000_2018-06-25_scribd_manual_xlsx.csv", "Scribd manual XLSX extraction of Russell 2000 2018 list"),
            Anchor(2019, "2019-07-01", ANCHOR_DIR / "russell2000_2019-07-01_scribd_manual_pdf.csv", "Scribd manual PDF extraction of Russell 2000 2019 list"),
            Anchor(2021, "2021-06-28", ANCHOR_DIR / "russell2000_2021-06-28_scribd_manual_pdf.csv", "Scribd manual PDF extraction of Russell 2000 2021 list"),
            Anchor(2022, "2022-06-24", ANCHOR_DIR / "russell2000_2022-06-24_scribd_manual_pdf.csv", "Scribd manual PDF extraction of Russell 2000 2022 list"),
        ],
        "use_public_ru3000_deltas_after": None,
    },
}


def clean_symbol(value: object) -> str:
    return str(value).strip().upper()


def load_symbols(path: Path) -> set[str]:
    if not path.exists():
        raise FileNotFoundError(path)
    symbols: set[str] = set()
    with path.open("r", encoding="utf-8", newline="") as fh:
        sample = fh.read(2048)
        fh.seek(0)
        if "," in sample:
            reader = csv.DictReader(fh)
            if reader.fieldnames and "symbol" in {name.lower() for name in reader.fieldnames}:
                symbol_field = next(name for name in reader.fieldnames if name.lower() == "symbol")
                for row in reader:
                    symbol = clean_symbol(row.get(symbol_field, ""))
                    if symbol:
                        symbols.add(symbol)
                return symbols
        for line in fh:
            if not line.strip() or line.lower().startswith("symbol"):
                continue
            symbols.add(clean_symbol(line.split(",", 1)[0]))
    return symbols


def load_ru3000_delta_events() -> dict[int, dict[str, dict[str, set[str]]]]:
    if not EVENTS_CSV.exists():
        return {}
    df = pd.read_csv(EVENTS_CSV)
    df = df[df["stage"].astype(str).str.startswith("final")]
    events: dict[int, dict[str, dict[str, set[str]]]] = {}
    for (year, effective_date, action), group in df.groupby(["year", "effective_date", "action"]):
        year_events = events.setdefault(int(year), {})
        date_events = year_events.setdefault(str(effective_date), {"difference": set(), "union": set()})
        key = "difference" if str(action) == "deletions" else "union"
        date_events[key].update(clean_symbol(s) for s in group["symbol"].tolist() if clean_symbol(s))
    return events


def anchor_by_year(anchors: list[Anchor]) -> dict[int, tuple[Anchor, set[str]]]:
    loaded = {}
    for anchor in anchors:
        loaded[anchor.year] = (anchor, load_symbols(anchor.path))
    return loaded


def metadata_for_year(index: str, year: int, status: str, sources: list[str]) -> dict:
    return {
        "index": index,
        "confidence": status,
        "source_notes": sources,
        "warning": (
            "Public-source PIT scaffold. Years without direct anchors are carried "
            "from nearest collected membership and are not true historical membership."
        ),
    }


def build_index(index: str) -> list[dict]:
    cfg = INDEXES[index]
    anchors = anchor_by_year(cfg["anchors"])
    years = range(2004, 2027)
    first_anchor_year = min(anchors)
    current = set(anchors[first_anchor_year][1])
    ru3000_events = load_ru3000_delta_events() if cfg["use_public_ru3000_deltas_after"] else {}
    report_rows = []
    out_dir = OUT_SRC / cfg["folder"]
    out_dir.mkdir(parents=True, exist_ok=True)

    for year in years:
        changes: dict[str, dict[str, list[str]]] = {}
        sources: list[str] = []

        if year < first_anchor_year:
            jan1 = set(anchors[first_anchor_year][1])
            status = f"backfilled_scaffold_from_{first_anchor_year}_anchor"
            sources.append(anchors[first_anchor_year][0].source)
            final = set(jan1)
        else:
            jan1 = set(current)
            status = "carried_forward_no_direct_public_anchor"

            if year in anchors:
                anchor, target = anchors[year]
                removed = sorted(jan1 - target)
                added = sorted(target - jan1)
                if removed or added:
                    changes[anchor.as_of] = {"difference": removed, "union": added}
                final = set(target)
                status = anchor.confidence
                sources.append(anchor.source)
            else:
                final = set(jan1)

            if cfg["use_public_ru3000_deltas_after"] and year > int(cfg["use_public_ru3000_deltas_after"]):
                status = "public_delta_derived_from_prior_anchor"
                for effective_date, event in sorted(ru3000_events.get(year, {}).items()):
                    removed = sorted(event["difference"])
                    added = sorted(event["union"])
                    if removed or added:
                        changes[effective_date] = {"difference": removed, "union": added}
                        final -= set(removed)
                        final |= set(added)
                sources.append("Official LSEG/FTSE Russell final Russell 3000 additions/deletions event CSV")

        data = {
            "year": year,
            "tickers_on_Jan_1": sorted(jan1),
            "changes": changes,
            "metadata": metadata_for_year(index, year, status, sources),
        }
        out_path = out_dir / f"{cfg['prefix']}-{year}.yaml"
        with out_path.open("w", encoding="utf-8") as fh:
            yaml.dump(
                data,
                fh,
                Dumper=IndentDumper,
                sort_keys=False,
                allow_unicode=False,
                default_flow_style=False,
            )

        current = set(final)
        report_rows.append(
            {
                "index": index,
                "year": year,
                "jan1_count": len(jan1),
                "final_count": len(final),
                "change_dates": len(changes),
                "status": status,
                "path": str(out_path.relative_to(REPO_ROOT)),
            }
        )
        print(f"{index} {year}: Jan1={len(jan1)} final={len(final)} changes={len(changes)} {status}")

    return report_rows


def main() -> int:
    all_rows: list[dict] = []
    for index in ("russell3000", "russell2000"):
        all_rows.extend(build_index(index))

    AUDIT_DIR.mkdir(exist_ok=True)
    report_path = AUDIT_DIR / "public_anchor_pit_build_report.csv"
    with report_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["index", "year", "jan1_count", "final_count", "change_dates", "status", "path"],
        )
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"wrote {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
