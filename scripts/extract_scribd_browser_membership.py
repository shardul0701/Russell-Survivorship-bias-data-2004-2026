"""Extract Russell membership anchors from browser-rendered Scribd captures."""

from __future__ import annotations

import argparse
import csv
import gzip
import html
import json
import re
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NORGATE_DIR = Path(r"C:\Users\shard\Light Water Internship\july-backtester-norgate-data\data")
SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.-]{0,9}$")
SKIP_PATTERNS = [
    "Russell US Indexes",
    "Membership list",
    "Russell 3000",
    "Company",
    "Ticker",
    "Download to read",
    "You are on page",
    "Zoom",
    "Ad",
]
CONTENT_URL_RE = re.compile(r'https://html\.scribdassets\.com/[^"\']+?/pages/(\d+)-[a-f0-9]+\.jsonp')
TOKEN_URL_RE = re.compile(r'(https://html\.scribdassets\.com/[^"\']+?/pages/(\d+)-[a-f0-9]+\.jsonp\?token=[^"\']+)')


def load_candidates(extra_paths: list[Path], norgate_dir: Path) -> set[str]:
    symbols = set()
    if norgate_dir.exists():
        for path in norgate_dir.glob("*.parquet"):
            name = path.stem.upper()
            if name.startswith(("$", "#", "%")):
                continue
            if SYMBOL_RE.match(name):
                symbols.add(name)
    for path in extra_paths:
        if not path.exists():
            continue
        if path.suffix.lower() == ".csv":
            with open(path, newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                if reader.fieldnames and "symbol" in reader.fieldnames:
                    symbols.update(str(row["symbol"]).strip().upper() for row in reader)
                else:
                    fh.seek(0)
                    symbols.update(line.split(",")[0].strip().upper() for line in fh)
        else:
            symbols.update(line.strip().upper() for line in path.read_text(encoding="utf-8", errors="replace").splitlines())
    return {s for s in symbols if SYMBOL_RE.match(s)}


def split_row(line: str, candidates: set[str]) -> list[dict[str, str]]:
    compact = line.replace("\u00a0", "").strip()
    if not compact or any(pattern in compact for pattern in SKIP_PATTERNS):
        return []
    if not re.search(r"[A-Z]{2,}$", compact):
        return []

    suffixes = [s for s in candidates if compact.endswith(s) and len(compact) > len(s) + 4]
    if not suffixes:
        return []
    right_symbol = max(suffixes, key=len)
    before_right = compact[: -len(right_symbol)]

    options = []
    for left_symbol in candidates:
        idx = before_right.find(left_symbol)
        while idx >= 0:
            left_company = before_right[:idx].strip()
            right_company = before_right[idx + len(left_symbol) :].strip()
            if 2 <= len(left_company) <= 55 and 2 <= len(right_company) <= 75:
                if left_company[0].isdigit() or left_company[0].isalpha():
                    options.append((abs(len(left_company) - 22), -len(left_symbol), left_symbol, left_company, right_company))
            idx = before_right.find(left_symbol, idx + 1)
    if not options:
        return [{"symbol": right_symbol, "company": before_right, "side": "right_only"}]

    _, _, left_symbol, left_company, right_company = sorted(options)[0]
    return [
        {"symbol": left_symbol, "company": left_company, "side": "left"},
        {"symbol": right_symbol, "company": right_company, "side": "right"},
    ]


def parse_text(text: str, candidates: set[str]) -> list[dict[str, str]]:
    rows = []
    for line in text.splitlines():
        rows.extend(split_row(line, candidates))
    deduped = {}
    for row in rows:
        deduped.setdefault(row["symbol"], row)
    return sorted(deduped.values(), key=lambda row: row["symbol"])


def read_jsonp_page(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(b"\x1f\x8b"):
        raw = gzip.decompress(raw)
    text = raw.decode("utf-8", errors="replace")
    payload = text[text.find("(") + 1 : text.rfind(")")]
    return json.loads(payload)[0]


def download_jsonp_pages(rendered_html: str, cache_dir: Path) -> None:
    full_urls = {int(page): url for url, page in TOKEN_URL_RE.findall(rendered_html)}
    if not full_urls:
        return
    token = full_urls[sorted(full_urls)[0]].split("?token=", 1)[1]
    base_urls = sorted(set(CONTENT_URL_RE.finditer(rendered_html)), key=lambda match: int(match.group(1)))
    cache_dir.mkdir(parents=True, exist_ok=True)
    for match in base_urls:
        page_num = int(match.group(1))
        out_path = cache_dir / f"page_{page_num:02d}.jsonp"
        if out_path.exists() and out_path.stat().st_size:
            continue
        url = match.group(0)
        if "?token=" not in url:
            url = f"{url}?token={token}"
        data = urllib.request.urlopen(url, timeout=30).read()
        out_path.write_bytes(data)


def iter_text_with_width_markers(node: Tag) -> str:
    parts: list[str] = []

    def walk(current: Tag) -> None:
        for child in current.children:
            if isinstance(child, NavigableString):
                parts.append(str(child))
            elif isinstance(child, Tag):
                if "w" in (child.get("class") or []):
                    parts.append("|")
                walk(child)

    walk(node)
    return html.unescape("".join(parts)).replace("\xa0", " ").strip()


def style_px(style: str, key: str) -> int | None:
    match = re.search(rf"{key}:(\d+)px", style)
    return int(match.group(1)) if match else None


def clean_field(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def row_parts_from_span(span: Tag) -> list[str]:
    marked = iter_text_with_width_markers(span)
    parts = [clean_field(part) for part in marked.split("|") if clean_field(part)]
    if len(parts) != 1:
        return parts
    pieces = parts[0].rsplit(" ", 1)
    if len(pieces) == 2 and SYMBOL_RE.match(pieces[1].upper()):
        return [pieces[0], pieces[1]]
    return parts


def parse_page_html(page_num: int, page_html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(page_html, "html.parser")
    rows: list[dict[str, str]] = []
    for span in soup.find_all("span", class_="a"):
        style = span.get("style", "")
        top = style_px(style, "top")
        left = style_px(style, "left")
        if top is None or left is None or top < 600 or top > 5400 or left > 2600:
            continue
        parts = row_parts_from_span(span)
        if len(parts) not in (2, 4):
            continue
        for idx in range(0, len(parts), 2):
            company, symbol = parts[idx], parts[idx + 1].upper()
            if not SYMBOL_RE.match(symbol):
                continue
            if company != company.upper() or symbol.endswith("."):
                continue
            if any(pattern in company for pattern in SKIP_PATTERNS):
                continue
            rows.append(
                {
                    "symbol": symbol,
                    "company": company,
                    "side": "left" if idx == 0 else "right",
                    "page": str(page_num),
                    "row_top": str(top),
                }
            )
    return rows


def parse_rendered_html(rendered_html: str, jsonp_dir: Path | None, download_pages: bool) -> list[dict[str, str]]:
    if jsonp_dir and download_pages:
        download_jsonp_pages(rendered_html, jsonp_dir)

    page_htmls: dict[int, str] = {}
    soup = BeautifulSoup(rendered_html, "html.parser")
    for page in soup.find_all("div", class_="newpage"):
        page_id = page.get("id", "")
        match = re.fullmatch(r"page(\d+)", page_id)
        if match and page.find("div", class_="text_layer"):
            page_htmls[int(match.group(1))] = str(page)

    if jsonp_dir:
        for path in sorted(jsonp_dir.glob("page_*.jsonp")):
            match = re.search(r"page_(\d+)", path.stem)
            if match:
                page_htmls[int(match.group(1))] = read_jsonp_page(path)

    rows: list[dict[str, str]] = []
    for page_num, page_html in sorted(page_htmls.items()):
        rows.extend(parse_page_html(page_num, page_html))

    deduped = {}
    for row in rows:
        deduped.setdefault(row["symbol"], row)
    return sorted(deduped.values(), key=lambda row: row["symbol"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_file")
    parser.add_argument("--out", required=True)
    parser.add_argument("--extra-symbols", action="append", default=[])
    parser.add_argument("--norgate-dir", default=str(DEFAULT_NORGATE_DIR))
    parser.add_argument("--mode", choices=["text", "rendered-html"], default="text")
    parser.add_argument("--jsonp-dir")
    parser.add_argument("--download-jsonp", action="store_true")
    args = parser.parse_args()

    input_text = Path(args.input_file).read_text(encoding="utf-8", errors="replace")
    if args.mode == "rendered-html":
        rows = parse_rendered_html(input_text, Path(args.jsonp_dir) if args.jsonp_dir else None, args.download_jsonp)
        fieldnames = ["symbol", "company", "side", "page", "row_top"]
    else:
        candidates = load_candidates([Path(p) for p in args.extra_symbols], Path(args.norgate_dir))
        rows = parse_text(input_text, candidates)
        fieldnames = ["symbol", "company", "side"]
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {out_path}: {len(rows)} symbols")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
