import csv
import re
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TEXT_DIR = ROOT / "source_raw" / "manual_downloads" / "scribd_bundle_2026-07-25_text"
SECOND_TEXT_DIR = ROOT / "source_raw" / "manual_downloads" / "scribd_second_batch_2026-07-25_text"
SECOND_BATCH_DIR = ROOT / "source_raw" / "manual_downloads" / "scribd_second_batch_2026-07-25"
OUT_DIR = ROOT / "audit" / "extracted_public_sources" / "membership_anchors"
DELTA_DIR = ROOT / "audit" / "extracted_public_sources"

TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.]{0,6}$")
SPLIT_RE = re.compile(r"\s{2,}")


MEMBERSHIP_FILES = {
    "pdf-russell3000-membership-list-2011_compress.txt": ("Russell 3000", "2011-06-27", "russell3000_2011-06-27_scribd_manual_pdf.csv"),
    "pdf-ru3000-membershiplist-20160627_compress.txt": ("Russell 3000", "2016-06-27", "russell3000_2016-06-27_scribd_manual_pdf.csv"),
    "ilide.info-ru3000-membershiplist-20170626-pr_90f43cae764026263c9c14458b2d8f01.txt": ("Russell 3000", "2017-06-26", "russell3000_2017-06-26_scribd_manual_pdf.csv"),
    "ilide.info-ru3000-membershiplist-20180625-0-pr_567d6036fa16ec7def0658d2a18ab970.txt": ("Russell 3000", "2018-06-25", "russell3000_2018-06-25_scribd_manual_pdf.csv"),
    "ilide.info-ru3000-membershiplist-20190701-pr_424fb05f0a6e778ab57af5a185873cb7.txt": ("Russell 3000", "2019-07-01", "russell3000_2019-07-01_scribd_manual_pdf.csv"),
    "ilide.info-ru3000-membershiplist-20200629-pr_fea62487a92119e8fa7ca4336909e2ec.txt": ("Russell 3000", "2020-06-29", "russell3000_2020-06-29_scribd_manual_pdf.csv"),
    "ilide.info-ru3000-membershiplist-20210628-pr_09afa2c99b9aaf7f3d8ffae34376f00d.txt": ("Russell 3000", "2021-06-28", "russell3000_2021-06-28_scribd_manual_pdf.csv"),
    "ru3000-membershiplist-20220624-0_compress.txt": ("Russell 3000", "2022-06-24", "russell3000_2022-06-24_scribd_manual_pdf.csv"),
    "russell-3000-membership-list_compress.txt": ("Russell 3000", "2010-06-28", "russell3000_2010-06-28_scribd_manual_pdf.csv"),
    "russell-2000-membership-list-2013_compress.txt": ("Russell 2000", "2013-06-28", "russell2000_2013-06-28_scribd_manual_pdf.csv"),
    "ilide.info-russell-membership-2014-pr_ad072b1faf45b3431592051c56bd047f.txt": ("Russell 2000", "2014-06-27", "russell2000_2014-06-27_scribd_manual_pdf.csv"),
    "ru2000-membershiplist-20180625-0_compress.txt": ("Russell 2000", "2018-06-25", "russell2000_2018-06-25_scribd_manual_pdf.csv"),
    "ru2000-membershiplist-20190701_compress.txt": ("Russell 2000", "2019-07-01", "russell2000_2019-07-01_scribd_manual_pdf.csv"),
    "ru2000-membershiplist-20210628-1_compress.txt": ("Russell 2000", "2021-06-28", "russell2000_2021-06-28_scribd_manual_pdf.csv"),
    "ru2000-membershiplist-20220624-0-1_compress.txt": ("Russell 2000", "2022-06-24", "russell2000_2022-06-24_scribd_manual_pdf.csv"),
}

DELTA_FILES = {
    "russel-3000-deletions-2020_compress.txt": ("Russell 3000", "2020-06-26", "deletion", "russell3000_2020-06-26_deletions_scribd_manual_pdf.csv"),
    "russell-3000-index-additions-2021_compress.txt": ("Russell 3000", "2021-06-25", "addition", "russell3000_2021-06-25_additions_scribd_manual_pdf.csv"),
    "ru3000-additions-20250627_compress.txt": ("Russell 3000", "2025-06-27", "addition", "russell3000_2025-06-27_additions_scribd_manual_pdf.csv"),
    "ru3000-deletions-20250627_compress.txt": ("Russell 3000", "2025-06-27", "deletion", "russell3000_2025-06-27_deletions_scribd_manual_pdf.csv"),
}

SECOND_BATCH_MEMBERSHIP_FILES = {
    "russell3000-membership-list-2011_compress.txt": ("Russell 3000", "2011-06-27", "russell3000_2011-06-27_scribd_second_batch_pdf.csv"),
    "russell-3000-membership-list_compress.txt": ("Russell 3000", "2015-06-26", "russell3000_2015-06-26_scribd_second_batch_pdf.csv"),
    "ru3000-membershiplist-20160627_compress.txt": ("Russell 3000", "2016-06-27", "russell3000_2016-06-27_scribd_second_batch_pdf_symbol_check.csv"),
}

XLSX_MEMBERSHIP_FILES = {
    "625938539-ru2000-membershiplist-20180625-0.xlsx": ("Russell 2000", "2018-06-25", "russell2000_2018-06-25_scribd_manual_xlsx.csv"),
}


def valid_symbol(token: str) -> bool:
    if not TICKER_RE.match(token):
        return False
    return token not in {"INDEX", "TICKER", "SYMBOL", "PAGE", "INC", "CORP", "LTD", "THE"}


def clean_company(token: str) -> str:
    return " ".join(token.replace("\x0c", " ").split())


def parse_membership(path: Path):
    rows = []
    seen = set()
    for line_no, raw in enumerate(path.read_text(errors="ignore").splitlines(), 1):
        parts = [p.strip() for p in SPLIT_RE.split(raw.strip()) if p.strip()]
        if len(parts) < 2:
            continue
        for i in range(len(parts) - 1):
            company, symbol = clean_company(parts[i]), parts[i + 1].strip()
            if not valid_symbol(symbol):
                continue
            if company.upper() in {"COMPANY", "TICKER", "RUSSELL INDEXES.", "RUSSELL INDEXES"}:
                continue
            key = symbol
            if key in seen:
                continue
            seen.add(key)
            rows.append({"symbol": symbol, "company": company, "source_line": line_no})
    return sorted(rows, key=lambda r: r["symbol"])


def parse_delta(path: Path):
    rows = []
    seen = set()
    industries = {
        "Technology",
        "Industrials",
        "Consumer Discretionary",
        "Health Care",
        "Energy",
        "Financials",
        "Basic Materials",
        "Real Estate",
        "Consumer Staples",
        "Utilities",
        "Telecommunications",
    }
    for line_no, raw in enumerate(path.read_text(errors="ignore").splitlines(), 1):
        parts = [p.strip() for p in SPLIT_RE.split(raw.strip()) if p.strip()]
        if len(parts) < 2:
            continue
        company, symbol = clean_company(parts[0]), parts[1]
        if not valid_symbol(symbol):
            continue
        industry = parts[2] if len(parts) > 2 and parts[2] in industries else ""
        if symbol in seen:
            continue
        seen.add(symbol)
        rows.append({"symbol": symbol, "company": company, "industry": industry, "source_line": line_no})
    return sorted(rows, key=lambda r: r["symbol"])


def parse_xlsx_membership(path: Path):
    df = pd.read_excel(path, sheet_name=0, header=None, dtype=str)
    rows = []
    seen = set()
    pairs = [(0, 1), (2, 3)]
    for idx, row in df.iterrows():
        for company_col, symbol_col in pairs:
            company = row.get(company_col)
            symbol = row.get(symbol_col)
            if pd.isna(company) or pd.isna(symbol):
                continue
            company = clean_company(str(company))
            symbol = str(symbol).strip()
            if not valid_symbol(symbol):
                continue
            if company.upper() in {"COMPANY", "TICKER", "RUSSELL US INDEXES", "MEMBERSHIP LIST"}:
                continue
            if symbol in seen:
                continue
            seen.add(symbol)
            rows.append({"symbol": symbol, "company": company, "source_row": int(idx) + 1})
    return sorted(rows, key=lambda r: r["symbol"])


def write_csv(path: Path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_symbols(path: Path, rows):
    path.write_text("\n".join(row["symbol"] for row in rows) + "\n", encoding="utf-8")


def main():
    summary = []
    for filename, (index_name, as_of, out_name) in MEMBERSHIP_FILES.items():
        rows = parse_membership(TEXT_DIR / filename)
        out = OUT_DIR / out_name
        write_csv(out, rows, ["symbol", "company", "source_line"])
        write_symbols(out.with_name(out.stem.replace("_scribd_manual_pdf", "_symbols") + ".txt"), rows)
        summary.append((as_of, index_name, len(rows), out.relative_to(ROOT)))

    for filename, (index_name, as_of, action, out_name) in DELTA_FILES.items():
        rows = parse_delta(TEXT_DIR / filename)
        out = DELTA_DIR / out_name
        write_csv(out, rows, ["symbol", "company", "industry", "source_line"])
        summary.append((as_of, f"{index_name} {action}s", len(rows), out.relative_to(ROOT)))

    for filename, (index_name, as_of, out_name) in SECOND_BATCH_MEMBERSHIP_FILES.items():
        rows = parse_membership(SECOND_TEXT_DIR / filename)
        out = OUT_DIR / out_name
        write_csv(out, rows, ["symbol", "company", "source_line"])
        write_symbols(out.with_name(out.stem.replace("_scribd_second_batch_pdf_symbol_check", "_symbols").replace("_scribd_second_batch_pdf", "_symbols") + ".txt"), rows)
        summary.append((as_of, f"{index_name} second-batch", len(rows), out.relative_to(ROOT)))

    for filename, (index_name, as_of, out_name) in XLSX_MEMBERSHIP_FILES.items():
        rows = parse_xlsx_membership(SECOND_BATCH_DIR / filename)
        out = OUT_DIR / out_name
        write_csv(out, rows, ["symbol", "company", "source_row"])
        write_symbols(out.with_name(out.stem.replace("_scribd_manual_xlsx", "_symbols") + ".txt"), rows)
        summary.append((as_of, f"{index_name} manual-xlsx", len(rows), out.relative_to(ROOT)))

    for as_of, label, count, out in sorted(summary):
        print(f"{as_of} {label}: {count:4d} -> {out}")


if __name__ == "__main__":
    main()
