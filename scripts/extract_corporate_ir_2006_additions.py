"""Extract the 2006 Russell 3000 additions PDF mirrored on corporate-ir.net."""

from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path

import fitz


SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.]{0,7}$")


def extract_rows(pdf_path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    doc = fitz.open(pdf_path)
    for page_num, page in enumerate(doc, start=1):
        by_y: dict[int, list[tuple[float, str]]] = defaultdict(list)
        for x0, y0, _x1, _y1, text, _block, _line, _word in page.get_text("words"):
            if y0 < (350 if page_num == 1 else 35) or y0 > 742:
                continue
            by_y[round(y0 / 3) * 3].append((x0, text))

        for y, words in sorted(by_y.items()):
            cols = [[], [], [], []]
            for x, text in sorted(words):
                if 80 <= x < 210:
                    cols[0].append(text)
                elif 210 <= x < 255:
                    cols[1].append(text)
                elif 255 <= x < 382:
                    cols[2].append(text)
                elif 382 <= x < 430:
                    cols[3].append(text)

            for side in (0, 2):
                company = " ".join(cols[side]).strip()
                symbol = " ".join(cols[side + 1]).strip().replace(" ", ".")
                if company in ("", "Company") or symbol in ("", "Symbol"):
                    continue
                if SYMBOL_RE.match(symbol):
                    rows.append(
                        {
                            "symbol": symbol,
                            "company": company,
                            "side": "left" if side == 0 else "right",
                            "page": str(page_num),
                            "row_y": str(y),
                        }
                    )

    deduped = {}
    for row in rows:
        deduped.setdefault(row["symbol"], row)
    return sorted(deduped.values(), key=lambda row: row["symbol"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf_file")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    rows = extract_rows(Path(args.pdf_file))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["symbol", "company", "side", "page", "row_y"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {out_path}: {len(rows)} symbols")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
