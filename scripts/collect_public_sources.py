"""Collect public Russell reconstitution source documents.

The first public-source layer is FTSE Russell/LSEG annual Russell 3000
additions/deletions PDFs. These are not a full PIT index by themselves, but they
are official annual reconstitution deltas and give us a reproducible backbone.
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "source_raw" / "lseg_russell_reconstitution"
EXTRACT_DIR = REPO_ROOT / "audit" / "extracted_public_sources"


@dataclass(frozen=True)
class SourceDoc:
    year: int
    effective_date: str
    action: str
    stage: str
    url: str
    source_type: str = "annual_reconstitution"

    @property
    def filename(self) -> str:
        return f"{self.year}_{self.stage}_ru3000_{self.action}.pdf"


SEED_SOURCES = [
    SourceDoc(2026, "2026-06-29", "additions", "final", "https://www.lseg.com/content/dam/ftse-russell/en_us/documents/other/ru3000-additions-20260626.pdf"),
    SourceDoc(2026, "2026-06-29", "deletions", "final", "https://www.lseg.com/content/dam/ftse-russell/en_us/documents/other/ru3000-deletions-20260626.pdf"),
    SourceDoc(2025, "2025-06-30", "additions", "final", "https://www.lseg.com/content/dam/ftse-russell/en_us/documents/other/ru3000-additions-20250627.pdf"),
    SourceDoc(2025, "2025-06-30", "deletions", "final", "https://www.lseg.com/content/dam/ftse-russell/en_us/documents/other/ru3000-deletions-20250627.pdf"),
    SourceDoc(2024, "2024-07-01", "additions", "final", "https://www.lseg.com/content/dam/ftse-russell/en_us/documents/other/ru3000-additions-final-20240628.pdf"),
    SourceDoc(2024, "2024-07-01", "deletions", "final", "https://www.lseg.com/content/dam/ftse-russell/en_us/documents/other/ru3000-deletions-final-20240628.pdf"),
    SourceDoc(2023, "2023-06-26", "additions", "final", "https://www.lseg.com/content/dam/ftse-russell/en_us/documents/other/ru3000-additions-final-20230623.pdf"),
    SourceDoc(2023, "2023-06-26", "deletions", "final", "https://www.lseg.com/content/dam/ftse-russell/en_us/documents/other/ru3000-deletions-final-20230623.pdf"),
    SourceDoc(2026, "2026-03-23", "ipo_additions", "final_1q", "https://www.lseg.com/content/dam/ftse-russell/en_us/documents/other/final-ipo-additions-1-qtr-r3000.pdf", "quarterly_ipo"),
    SourceDoc(2025, "2025-09-22", "ipo_additions", "final_3q", "https://www.lseg.com/content/dam/ftse-russell/en_us/documents/other/final-ipo-additions-3-qtr-r3000.pdf", "quarterly_ipo"),
    SourceDoc(2025, "2025-12-22", "ipo_additions", "final_4q", "https://www.lseg.com/content/dam/ftse-russell/en_us/documents/other/final-ipo-additions-4-qtr-r3000.pdf", "quarterly_ipo"),
]

INDUSTRIES = [
    "Basic Materials",
    "Consumer Discretionary",
    "Consumer Staples",
    "Energy",
    "Financials",
    "Health Care",
    "Industrials",
    "Real Estate",
    "Technology",
    "Telecommunications",
    "Utilities",
]

TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.]{0,7}$")


def download(url: str, path: Path, overwrite: bool = False) -> bool:
    if path.exists() and not overwrite:
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(req, timeout=45) as response:
            data = response.read()
    except Exception as exc:
        print(f"WARN download failed: {url} ({exc})")
        return False
    if not data.startswith(b"%PDF"):
        print(f"WARN not a PDF: {url}")
        return False
    path.write_bytes(data)
    return True


def pdf_to_text(pdf_path: Path) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout


def parse_rows(text: str) -> list[dict[str, str]]:
    rows = []
    for raw_line in text.splitlines():
        line = " ".join(raw_line.strip().split())
        if not line or "Company Symbol Industry" in line:
            continue
        if any(skip in line for skip in ["Russell US Indexes", "Reconstitution", "FTSE Russell", "lseg.com", "CORPORATE", "For more information", "© "]):
            continue
        industry = next((ind for ind in INDUSTRIES if line.endswith(ind)), None)
        if industry is None:
            continue
        before = line[: -len(industry)].strip()
        parts = before.split()
        symbol_idx = None
        for i in range(len(parts) - 1, -1, -1):
            if TICKER_RE.match(parts[i]):
                symbol_idx = i
                break
        if symbol_idx is None or symbol_idx == 0:
            continue
        company = " ".join(parts[:symbol_idx]).strip()
        symbol = parts[symbol_idx].strip()
        if company and symbol:
            rows.append({"company": company, "symbol": symbol, "industry": industry})
    return rows


def parse_ipo_rows(text: str) -> list[dict[str, str]]:
    body = " ".join(text.split())
    if "Effective " not in body or "Russell 3000" not in body:
        return []
    body = re.sub(r"^.*?Ticker Company Name", "", body)
    body = re.sub(r"Russell 3000.*$", "", body)
    tokens = body.split()
    rows = []
    current_symbol = None
    company_parts: list[str] = []
    for token in tokens:
        if TICKER_RE.match(token):
            if current_symbol and company_parts:
                rows.append({"company": " ".join(company_parts).strip(), "symbol": current_symbol, "industry": ""})
            current_symbol = token
            company_parts = []
        elif current_symbol:
            company_parts.append(token)
    if current_symbol and company_parts:
        rows.append({"company": " ".join(company_parts).strip(), "symbol": current_symbol, "industry": ""})
    return rows


def write_csv(path: Path, rows: list[dict[str, str]], source: SourceDoc, url: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        fieldnames = ["year", "effective_date", "stage", "action", "source_type", "symbol", "company", "industry", "source_url"]
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "year": source.year,
                    "effective_date": source.effective_date,
                    "stage": source.stage,
                    "action": source.action,
                    "source_type": source.source_type,
                    "symbol": row["symbol"],
                    "company": row["company"],
                    "industry": row["industry"],
                    "source_url": url,
                }
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    manifest_rows = []
    all_rows = []
    for source in SEED_SOURCES:
        pdf_path = RAW_DIR / str(source.year) / source.filename
        ok = download(source.url, pdf_path, overwrite=args.overwrite)
        status = "downloaded" if ok else "missing"
        n_rows = 0
        if ok:
            text = pdf_to_text(pdf_path)
            txt_path = pdf_path.with_suffix(".txt")
            txt_path.write_text(text, encoding="utf-8")
            rows = parse_ipo_rows(text) if source.source_type == "quarterly_ipo" else parse_rows(text)
            n_rows = len(rows)
            csv_path = EXTRACT_DIR / f"{source.year}_{source.stage}_ru3000_{source.action}.csv"
            write_csv(csv_path, rows, source, source.url)
            all_rows.extend(
                {
                    **row,
                    "year": source.year,
                    "effective_date": source.effective_date,
                    "stage": source.stage,
                    "action": source.action,
                    "source_type": source.source_type,
                    "source_url": source.url,
                }
                for row in rows
            )
            print(f"{source.year} {source.action}: {n_rows} rows")
        manifest_rows.append(
            {
                "year": source.year,
                "effective_date": source.effective_date,
                "stage": source.stage,
                "action": source.action,
                "source_type": source.source_type,
                "url": source.url,
                "local_pdf": str(pdf_path.relative_to(REPO_ROOT)),
                "status": status,
                "rows_extracted": n_rows,
            }
        )

    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    with open(EXTRACT_DIR / "source_manifest.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(manifest_rows[0]))
        writer.writeheader()
        writer.writerows(manifest_rows)

    with open(EXTRACT_DIR / "ru3000_public_reconstitution_events.csv", "w", newline="", encoding="utf-8") as fh:
        fieldnames = ["year", "effective_date", "stage", "action", "source_type", "symbol", "company", "industry", "source_url"]
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in all_rows:
            writer.writerow({field: row[field] for field in fieldnames})

    print(f"wrote {EXTRACT_DIR / 'source_manifest.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
