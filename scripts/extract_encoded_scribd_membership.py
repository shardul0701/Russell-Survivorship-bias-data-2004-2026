"""Decode older Scribd Russell membership JSONP pages that use custom fonts."""

from __future__ import annotations

import argparse
import csv
import gzip
import html
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag


SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.-]{0,9}$")

PLAIN_LEFT_ANCHORS = {
    "2017": [
        "1-800 FLOWERS COM FLWS",
        "1ST SOURCE CORP SRCE",
        "21ST CENTURY FOX CL A FOXA",
        "21ST CENTURY FOX CL B FOX",
        "2U INC TWOU",
        "3D SYSTEMS CORP DDD",
        "3M CO MMM",
        "8X8 INC NEW EGHT",
        "A V HOMES INC AVHI",
        "A10 NETWORKS INC ATEN",
        "AAC HOLDINGS INC AAC",
        "AAON INC AAON",
        "AAR CORP AIR",
        "AARONS INC AAN",
        "ABAXIS INC ABAX",
        "ABBOTT LABORATORIES ABT",
        "ABBVIE INC ABBV",
        "ABEONA THERAPEUTICS INC ABEO",
        "ABERCROMBIE & FITCH ANF",
        "ABIOMED INC ABMD",
        "ABM INDUSTRIES INC ABM",
        "ABRAXAS PETE CORP AXAS",
        "ACACIA COMMUNICATIONS ACIA",
        "ACACIA RESEARCH CORP ACTG",
        "ACADIA HEALTHCARE CO ACHC",
        "ACADIA PHARMACEUTICALS ACAD",
        "ACADIA REALTY TRUST AKR",
        "ACCELERATE DIAGNOSTICS AXDX",
        "ACCELERON PHARMA INC XLRN",
        "ACCENTURE PLC IRELAND ACN",
        "ACCESS NATL CORP ANCX",
        "ACCO BRANDS CORP ACCO",
        "ACCURAY INC ARAY",
        "ACETO CORP ACET",
        "ACHAOGEN INC AKAO",
        "ACHILLION PHARM ACHN",
        "ACI WORLDWIDE INC ACIW",
        "ACLARIS THERAPEUTICS ACRS",
        "ACNB CORP ACNB",
        "ACORDA THERAPEUTICS INC ACOR",
        "ACTIVISION BLIZZARD INC ATVI",
        "ACTUA CORPORATION ACTA",
        "ACTUANT CORP ATU",
        "ACUITY BRANDS INC AYI",
        "ACUSHNET HOLDINGS CORP GOLF",
        "ACXIOM CORP ACXM",
        "ADAMAS PHARMACEUTICALS ADMS",
        "ADAMS RESOURCES & ENERGY AE",
    ],
    "2018": [
        "1-800 FLOWERS COM FLWS",
        "1ST CONSTITUTION BANCORP FCCY",
        "1ST SOURCE CORP SRCE",
        "21ST CENTURY FOX CL A FOXA",
        "21ST CENTURY FOX CL B FOX",
        "22ND CENTURY GROUP INC XXII",
        "2U INC TWOU",
        "3D SYSTEMS CORP DDD",
        "3M CO MMM",
        "8X8 INC NEW EGHT",
        "A V HOMES INC AVHI",
        "A10 NETWORKS INC ATEN",
        "AAC HOLDINGS INC AAC",
        "AAON INC AAON",
        "AAR CORP AIR",
        "AARONS INC AAN",
        "ABAXIS INC ABAX",
        "ABBOTT LABORATORIES ABT",
        "ABBVIE INC ABBV",
        "ABEONA THERAPEUTICS INC ABEO",
        "ABERCROMBIE & FITCH ANF",
        "ABIOMED INC ABMD",
        "ABM INDUSTRIES INC ABM",
        "ABRAXAS PETE CORP AXAS",
        "ACACIA COMMUNICATIONS ACIA",
        "ACACIA RESEARCH CORP ACTG",
        "ACADIA HEALTHCARE CO ACHC",
        "ACADIA PHARMACEUTICALS ACAD",
        "ACADIA REALTY TRUST AKR",
        "ACCELERATE DIAGNOSTICS AXDX",
        "ACCELERON PHARMA INC XLRN",
        "ACCENTURE PLC IRELAND ACN",
        "ACCESS NATL CORP ANCX",
        "ACCO BRANDS CORP ACCO",
        "ACCURAY INC ARAY",
        "ACHAOGEN INC AKAO",
        "ACHILLION PHARM ACHN",
        "ACI WORLDWIDE INC ACIW",
        "ACLARIS THERAPEUTICS ACRS",
        "ACM RESEARCH ACMR",
        "ACNB CORP ACNB",
        "ACORDA THERAPEUTICS INC ACOR",
        "ACTIVISION BLIZZARD INC ATVI",
        "ACTUANT CORP ATU",
        "ACUITY BRANDS INC AYI",
        "ACUSHNET HOLDINGS CORP GOLF",
        "ACXIOM CORP ACXM",
        "ADAMAS PHARMACEUTICALS ADMS",
    ],
    "2019": [
        "1-800 FLOWERS COM FLWS",
        "1ST CONSTITUTION BANCORP FCCY",
        "1ST SOURCE CORP SRCE",
        "22ND CENTURY GROUP INC XXII",
        "2U INC TWOU",
        "3D SYSTEMS CORP DDD",
        "3M CO MMM",
        "8X8 INC NEW EGHT",
        "A10 NETWORKS INC ATEN",
        "AAON INC AAON",
        "AAR CORP AIR",
        "AARONS INC AAN",
        "ABBOTT LABORATORIES ABT",
        "ABBVIE INC ABBV",
        "ABEONA THERAPEUTICS INC ABEO",
        "ABERCROMBIE & FITCH ANF",
        "ABIOMED INC ABMD",
        "ABM INDUSTRIES INC ABM",
        "ABRAXAS PETE CORP AXAS",
        "ACACIA COMMUNICATIONS ACIA",
        "ACACIA RESEARCH CORP ACTG",
        "ACADIA HEALTHCARE CO ACHC",
        "ACADIA PHARMACEUTICALS ACAD",
        "ACADIA REALTY TRUST AKR",
        "ACCELERATE DIAGNOSTICS AXDX",
        "ACCELERON PHARMA INC XLRN",
        "ACCENTURE PLC IRELAND ACN",
        "ACCO BRANDS CORP ACCO",
        "ACCURAY INC ARAY",
        "ACELRX PHARMACEUTICALS ACRX",
        "ACER THERAPEUTICS INC ACER",
        "ACHILLION PHARM ACHN",
        "ACI WORLDWIDE INC ACIW",
        "ACLARIS THERAPEUTICS ACRS",
        "ACNB CORP ACNB",
        "ACORDA THERAPEUTICS INC ACOR",
        "ACTIVISION BLIZZARD INC ATVI",
        "ACTUANT CORP ATU",
        "ACUITY BRANDS INC AYI",
        "ACUSHNET HOLDINGS CORP GOLF",
        "ADAMAS PHARMACEUTICALS ADMS",
        "ADDUS HOMECARE CORP ADUS",
        "ADESTO TECHNOLOGIES CORP IOTS",
        "ADIENT PLC ADNT",
        "ADMA BIOLOGICS INC ADMA",
        "ADOBE INC ADBE",
        "ADT INC ADT",
        "ADTALEM GLOBAL EDUCATION ATGE",
    ],
}


def read_jsonp_page(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(b"\x1f\x8b"):
        raw = gzip.decompress(raw)
    text = raw.decode("utf-8", errors="replace")
    return json.loads(text[text.find("(") + 1 : text.rfind(")")])[0]


def marked_text(node: Tag) -> str:
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


def page_entries(page_html: str) -> list[tuple[int, int, str]]:
    soup = BeautifulSoup(page_html, "html.parser")
    entries = []
    for span in soup.find_all("span", class_="a"):
        style = span.get("style", "")
        top = style_px(style, "top")
        left = style_px(style, "left")
        if top is None or left is None or top < 1200 or top > 5400:
            continue
        text = marked_text(span)
        if "|" not in text:
            continue
        entries.append((top, left, text))
    return sorted(entries)


def derive_map(year: str, jsonp_dir: Path) -> dict[str, str]:
    encoded_left = [text.replace("|", "") for _top, left, text in page_entries(read_jsonp_page(jsonp_dir / "page_01.jsonp")) if left < 500]
    plain_left = PLAIN_LEFT_ANCHORS[year]
    mapping = {" ": " "}
    conflicts = []
    for encoded, plain in zip(encoded_left, plain_left):
        if len(encoded) != len(plain):
            raise ValueError(f"anchor length mismatch: {encoded!r} vs {plain!r}")
        for enc_char, plain_char in zip(encoded, plain):
            existing = mapping.get(enc_char)
            if existing and existing != plain_char:
                conflicts.append((enc_char, existing, plain_char, encoded, plain))
            mapping[enc_char] = plain_char
    if conflicts:
        raise ValueError(f"mapping conflicts: {conflicts[:5]}")
    return mapping


def decode_text(text: str, mapping: dict[str, str]) -> str:
    return "".join(mapping.get(char, char) for char in text)


def split_entry(decoded: str) -> tuple[str, str] | None:
    parts = [part.strip() for part in decoded.split("|") if part.strip()]
    if len(parts) == 2 and SYMBOL_RE.match(parts[1]):
        return parts[0], parts[1]
    pieces = decoded.rsplit(" ", 1)
    if len(pieces) == 2 and SYMBOL_RE.match(pieces[1]):
        return pieces[0].strip(), pieces[1]
    return None


def extract(year: str, jsonp_dir: Path) -> list[dict[str, str]]:
    mapping = derive_map(year, jsonp_dir)
    rows = []
    for path in sorted(jsonp_dir.glob("page_*.jsonp")):
        page_num = int(re.search(r"page_(\d+)", path.stem).group(1))
        for top, left, encoded in page_entries(read_jsonp_page(path)):
            decoded = decode_text(encoded, mapping)
            split = split_entry(decoded)
            if not split:
                continue
            company, symbol = split
            if company != company.upper() or len(company) < 2:
                continue
            rows.append({"symbol": symbol, "company": company, "side": "left" if left < 1600 else "right", "page": str(page_num), "row_top": str(top)})
    deduped = {}
    for row in rows:
        deduped.setdefault(row["symbol"], row)
    return sorted(deduped.values(), key=lambda row: row["symbol"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", required=True, choices=sorted(PLAIN_LEFT_ANCHORS))
    parser.add_argument("--jsonp-dir", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    rows = extract(args.year, Path(args.jsonp_dir))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["symbol", "company", "side", "page", "row_top"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {out}: {len(rows)} symbols")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
