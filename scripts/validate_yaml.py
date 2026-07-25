"""Validate generated Russell PIT YAML files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
INDEXES = {
    "russell1000": ("russell_1000_ticker_history", "russell-1000-ticker-changes", 850, 1250),
    "russell2000": ("russell_2000_ticker_history", "russell-2000-ticker-changes", 1500, 2300),
    "russell3000": ("russell_3000_ticker_history", "russell-3000-ticker-changes", 2400, 3600),
}


def normalize_index(index: str) -> str:
    key = index.strip().lower().replace("-", "").replace("_", "").replace(" ", "")
    aliases = {"rut": "russell2000", "rty": "russell2000", "rui": "russell1000", "rua": "russell3000"}
    return aliases.get(key, key)


def load_year(index: str, year: int) -> tuple[dict | None, Path]:
    folder, prefix, _, _ = INDEXES[index]
    path = REPO_ROOT / "src" / folder / f"{prefix}-{year}.yaml"
    if not path.exists():
        return None, path
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}, path


def final_membership(data: dict) -> list[str]:
    current = set(data.get("tickers_on_Jan_1", []))
    for _, entry in sorted((data.get("changes") or {}).items()):
        current -= set(entry.get("difference", []))
        current |= set(entry.get("union", []))
    return sorted(current)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", default="russell2000")
    args = parser.parse_args()
    index = normalize_index(args.index)
    if index not in INDEXES:
        parser.error(f"unsupported index {args.index!r}")

    _, _, min_members, max_members = INDEXES[index]
    all_ok = True
    prior_final = None
    prior_year = None

    print(f"{index} YAML validation")
    for year in range(2004, 2027):
        data, path = load_year(index, year)
        if data is None:
            print(f"FAIL {path.name}: missing")
            all_ok = False
            continue

        errors = []
        jan1 = data.get("tickers_on_Jan_1", [])
        if data.get("year") != year:
            errors.append(f"year field {data.get('year')!r} != {year}")
        if jan1 != sorted(set(jan1)):
            errors.append("tickers_on_Jan_1 is unsorted or has duplicates")
        if not (min_members <= len(jan1) <= max_members):
            errors.append(f"Jan-1 count {len(jan1)} outside expected {min_members}-{max_members}")
        for date_str, entry in (data.get("changes") or {}).items():
            if not str(date_str).startswith(str(year)):
                errors.append(f"change date {date_str} outside file year")
            for key in ("difference", "union"):
                values = entry.get(key, [])
                if values != sorted(set(values)):
                    errors.append(f"{date_str} {key} unsorted or duplicate")

        if prior_final is not None and sorted(jan1) != prior_final:
            missing = sorted(set(prior_final) - set(jan1))[:8]
            extra = sorted(set(jan1) - set(prior_final))[:8]
            errors.append(f"{prior_year}->{year} continuity mismatch missing={missing} extra={extra}")

        if errors:
            all_ok = False
            print(f"FAIL {path.name}")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"PASS {path.name}: {len(jan1)} Jan-1 members")

        prior_final = final_membership(data)
        prior_year = year

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
