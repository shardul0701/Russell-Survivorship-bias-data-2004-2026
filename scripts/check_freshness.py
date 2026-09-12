"""Report how current each Russell PIT change series is, and fail when one has
gone quiet for longer than the index's own publication cadence can explain.

Why the threshold is NOT calibrated on this repo's own change history
--------------------------------------------------------------------
The obvious rule -- "warn when the newest membership change is more than N days
old" -- measures a property of the INDEX, not of the repository, and the two
come apart badly here. The collected Russell 3000 series has 371- and 364-day
gaps in it (2023-06-26 -> 2024-07-01 -> 2025-06-30), but those are COLLECTION
gaps: only the annual reconstitution was gathered for those years. FTSE Russell
itself was publishing membership changes every quarter throughout. Calibrating
on the observed series would therefore set a ~400-day threshold and the check
would sleep through a full year of missed quarters.

So the threshold comes from the publisher's cadence instead. FTSE Russell adds
eligible IPOs to the Russell US indexes quarterly, effective the third Friday
of March, June, September and December, and runs the annual reconstitution each
June. Consecutive events are therefore at most ~92 days apart. 120 days leaves
room for a late notice and a delayed collection run without ever tolerating a
wholly skipped quarter.

Russell 2000 is a deliberate, acknowledged exception rather than a tuned
threshold. Its 2023-2026 rosters are a single fabricated block (one Jan-1
snapshot stamped across four year-labels) and its newest genuine dated change
is 2022-06-24. That cannot be repaired by re-running a collector -- it needs a
new membership anchor, which LSEG does not publish as a free additions/
deletions PDF the way it does for the Russell 3000. Silencing it with a big
number would hide the reason; it is silenced by name, with the reason and the
tracking issue attached, so the note changes the moment an anchor lands.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]

INDEXES = {
    # name: (folder, file prefix, max quiet days, acknowledged-stale reason)
    "russell3000": (
        "russell_3000_ticker_history",
        "russell-3000-ticker-changes",
        120,
        None,
    ),
    "russell2000": (
        "russell_2000_ticker_history",
        "russell-2000-ticker-changes",
        120,
        "2023-2026 rosters are a known fabricated block (one Jan-1 snapshot "
        "stamped across four year-labels); the newest genuine change is "
        "2022-06-24. Needs a new membership anchor, not a collector re-run. "
        "Tracked at zachisit/july-backtester-private-strategies#68.",
    ),
}


def newest_change(index: str) -> tuple[str | None, int]:
    folder, prefix, _, _ = INDEXES[index]
    dates: list[str] = []
    for year in range(2004, 2027):
        path = REPO_ROOT / "src" / folder / f"{prefix}-{year}.yaml"
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        dates.extend(str(k) for k in (data.get("changes") or {}))
    return (max(dates) if dates else None), len(dates)


def check(index: str) -> bool:
    _, _, max_quiet, acknowledged = INDEXES[index]
    latest, total = newest_change(index)
    print(f"{index}: {total} dated changes, newest {latest or 'none'}")

    if latest is None:
        print(f"  FAIL {index}: no dated membership changes at all")
        return False

    age = (date.today() - date.fromisoformat(latest)).days
    if age < 0:
        # a change can be published as final before it takes effect -- the
        # quarterly IPO additions are announced roughly two weeks ahead
        print(f"  newest change is announced but not yet effective "
              f"(in {-age} days); nothing is stale")
        return True
    print(f"  age {age} days (threshold {max_quiet})")

    if acknowledged:
        print(f"  NOTE {index} is acknowledged stale, not an alarm: {acknowledged}")
        return True
    if age > max_quiet:
        print(
            f"  FAIL {index}: {age} days since the newest membership change, "
            f"longer than the quarterly publication cadence can explain -- "
            f"re-run the public-source collection (scripts/collect_public_sources.py, "
            f"scripts/extract_membership_pdf.py) and rebuild"
        )
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", default="all", choices=["all", *INDEXES])
    args = parser.parse_args()
    names = list(INDEXES) if args.index == "all" else [args.index]
    return 0 if all([check(n) for n in names]) else 1


if __name__ == "__main__":
    sys.exit(main())
