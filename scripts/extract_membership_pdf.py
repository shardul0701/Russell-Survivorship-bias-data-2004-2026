"""Extract ticker anchors from Russell membership-list PDFs.

The 2016 public PDF uses two company/ticker columns. In pdftotext layout output,
the left ticker column is offset two rows above its company-name column, while
the right column remains aligned.
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
from pathlib import Path


TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.]{0,7}(?:\.[A-Z])?$")


def ensure_text(pdf_path: Path) -> Path:
    txt_path = pdf_path.with_suffix(".txt")
    if not txt_path.exists() or txt_path.stat().st_mtime < pdf_path.stat().st_mtime:
        subprocess.run(["pdftotext", "-layout", str(pdf_path), str(txt_path)], check=True)
    return txt_path


def split_line(line: str) -> tuple[str, str, str, str] | None:
    if not line.strip() or "Russell " in line or "Membership list" in line or "June " in line:
        return None
    if line.lstrip().startswith("Company"):
        line = " " * line.index("Company") + line.replace("Company", "", 1)
    left_company = line[:26].strip()
    left_ticker = line[26:34].strip()
    right_block = line[34:].strip()
    right_parts = right_block.split()
    right_ticker = right_parts[-1] if right_parts and not right_parts[-1].isdigit() else ""
    right_company = right_block[: -len(right_ticker)].strip() if right_ticker else ""
    return left_company, left_ticker, right_company, right_ticker


def parse_membership_text(text: str) -> list[dict[str, str]]:
    parsed = [split_line(line) for line in text.splitlines()]
    rows = []
    for i, item in enumerate(parsed):
        if item is None:
            continue
        left_company, left_ticker, right_company, right_ticker = item
        if right_company and TICKER_RE.match(right_ticker):
            rows.append({"symbol": right_ticker, "company": right_company, "side": "right"})
        if TICKER_RE.match(left_ticker):
            company = ""
            if i + 2 < len(parsed) and parsed[i + 2] is not None:
                company = parsed[i + 2][0]
            if company:
                rows.append({"symbol": left_ticker, "company": company, "side": "left_offset_2"})
    deduped = {}
    for row in rows:
        deduped.setdefault(row["symbol"], row)
    return sorted(deduped.values(), key=lambda row: row["symbol"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    txt_path = ensure_text(pdf_path)
    rows = parse_membership_text(txt_path.read_text(encoding="utf-8", errors="replace"))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["symbol", "company", "side"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {out_path}: {len(rows)} symbols")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
