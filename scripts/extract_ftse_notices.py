"""Extract Russell 3000 action lines from FTSE Russell notice PDFs."""

from __future__ import annotations

import csv
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
NOTICE_DIR = REPO_ROOT / "source_raw" / "ftse_index_notices"
OUT_PATH = REPO_ROOT / "audit" / "extracted_public_sources" / "ftse_notice_ru3000_actions.csv"

LINE_RE = re.compile(
    r"^(?P<symbol>[A-Z][A-Z0-9.]{0,7})\s*[-\u00ad]\s*will\s+(?P<action>be added|be deleted|no longer be added)\s+to\s+the\s+Russell\s+3000",
    re.IGNORECASE,
)


def extract_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted(NOTICE_DIR.glob("notice_*.txt")):
        notice_id = path.stem.replace("notice_", "")
        for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = " ".join(raw_line.strip().split())
            match = LINE_RE.match(line)
            if not match:
                continue
            action = match.group("action").lower()
            normalized = {
                "be added": "add",
                "be deleted": "delete",
                "no longer be added": "cancel_add",
            }[action]
            rows.append(
                {
                    "notice_id": notice_id,
                    "symbol": match.group("symbol").upper(),
                    "notice_action": normalized,
                    "raw_line": line,
                    "source_url": f"https://research.ftserussell.com/products/index-notices/home/getnotice/?id={notice_id}",
                }
            )
    return rows


def main() -> int:
    rows = extract_rows()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["notice_id", "symbol", "notice_action", "raw_line", "source_url"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {OUT_PATH}: {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
