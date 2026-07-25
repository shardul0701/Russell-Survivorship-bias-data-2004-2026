"""Extract Russell membership rows from Yumpu indexed text pages."""

from __future__ import annotations

import argparse
import csv
import html
import re
from pathlib import Path
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.-]{0,9}$")
DEFAULT_NORGATE_DIR = Path(r"C:\Users\shard\Light Water Internship\july-backtester-norgate-data\data")
HEADER_RE = re.compile(
    r"As of \d{2}/\d{2}/\d{4} .*? Company Ticker ",
    flags=re.IGNORECASE,
)


def fetch(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def page_urls(base_url: str, html_text: str) -> list[str]:
    soup = BeautifulSoup(html_text, "html.parser")
    urls = {base_url}
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if href.startswith(base_url.rstrip("/") + "/"):
            urls.add(href)
    return sorted(urls, key=lambda url: int(url.rstrip("/").split("/")[-1]) if url.rstrip("/").split("/")[-1].isdigit() else 1)


def extract_text_blocks(html_text: str, expected_index: str) -> list[str]:
    soup = BeautifulSoup(html_text, "html.parser")
    blocks = []
    expected_terms = [term for term in expected_index.split() if term]
    for p in soup.find_all("p"):
        raw = html.unescape(str(p))
        raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.IGNORECASE)
        text = BeautifulSoup(raw, "html.parser").get_text("\n")
        flat = re.sub(r"\s+", " ", text)
        if "Company" in flat and "Ticker" in flat and all(term in flat for term in expected_terms):
            blocks.append(text)
    return blocks


def load_candidates(norgate_dir: Path, extra_symbols: list[Path]) -> set[str]:
    symbols = set()
    if norgate_dir.exists():
        for path in norgate_dir.glob("*.parquet"):
            symbol = path.stem.upper().split("-", 1)[0]
            if not symbol.startswith(("$", "#", "%")) and SYMBOL_RE.fullmatch(symbol):
                symbols.add(symbol)
    for path in extra_symbols:
        if path.exists():
            symbols.update(
                line.strip().split(",", 1)[0].upper()
                for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            )
    return {symbol for symbol in symbols if SYMBOL_RE.fullmatch(symbol)}


def parse_line_rows(blocks: list[str]) -> dict[str, dict[str, str]]:
    rows = {}
    for block in blocks:
        for line in block.splitlines():
            line = re.sub(r"\s+", " ", line.replace("\xa0", " ")).strip()
            if not line or "Company" in line or "Ticker" in line or "Russell" in line:
                continue
            parts = line.rsplit(" ", 1)
            if len(parts) != 2:
                continue
            company, symbol = parts[0].strip(), parts[1].strip().upper()
            if SYMBOL_RE.fullmatch(symbol) and company and company == company.upper():
                rows.setdefault(symbol, {"symbol": symbol, "company": company})
    return rows


def parse_packed_rows(blocks: list[str], candidates: set[str]) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    for block in blocks:
        text = BeautifulSoup(html.unescape(block), "html.parser").get_text(" ")
        text = HEADER_RE.sub(" ", text)
        text = text.replace("Company Ticker", " ")
        tokens = re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip().split()
        company_tokens: list[str] = []
        for token in tokens:
            clean = token.strip().upper()
            if clean in candidates and company_tokens:
                company = " ".join(company_tokens).strip()
                if len(company) >= 3 and company == company.upper():
                    rows.setdefault(clean, {"symbol": clean, "company": company})
                company_tokens = []
            else:
                company_tokens.append(token)
    return rows


def parse_blocks(blocks: list[str], candidates: set[str]) -> list[dict[str, str]]:
    rows = parse_line_rows(blocks)
    if len(rows) < 1000 and candidates:
        rows = parse_packed_rows(blocks, candidates)
    return sorted(rows.values(), key=lambda row: row["symbol"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--index", required=True, help="Expected page text, e.g. Russell 2000")
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--norgate-dir", default=str(DEFAULT_NORGATE_DIR))
    parser.add_argument("--extra-symbols", action="append", default=[])
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)

    first = fetch(args.url)
    (raw_dir / "page_01.html").write_text(first, encoding="utf-8")

    all_blocks = extract_text_blocks(first, args.index)
    for idx, url in enumerate(page_urls(args.url, first), start=1):
        if url == args.url:
            continue
        text = fetch(url)
        (raw_dir / f"page_{idx:02d}.html").write_text(text, encoding="utf-8")
        all_blocks.extend(extract_text_blocks(text, args.index))

    candidates = load_candidates(Path(args.norgate_dir), [Path(path) for path in args.extra_symbols])
    rows = parse_blocks(all_blocks, candidates)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["symbol", "company"])
        writer.writeheader()
        writer.writerows(rows)

    symbols_out = out.with_name(out.stem.replace("_yumpu", "") + "_symbols.txt")
    symbols_out.write_text("\n".join(row["symbol"] for row in rows) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} rows to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
