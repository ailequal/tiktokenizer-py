"""Refresh the bundled price snapshot from OpenAI's official documentation pages.

Run with ``just prices-update``. The pages are fetched, parsed and checked; if anything does
not match the expected layout the script prints the problems and exits with an error, leaving
the current snapshot untouched. Otherwise it writes the new snapshot and lists what changed,
ready to review with ``git diff`` and commit.
"""

import sys
from pathlib import Path

from tiktokenizer_py import catalogue, prices

SNAPSHOT = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "tiktokenizer_py"
    / "data"
    / prices.SNAPSHOT_FILE
)


def main() -> int:
    model_ids = [e.id for e in catalogue.entries() if e.kind == "model"]
    print(f"fetching {prices.PRICING_URL} and {len(model_ids)} model pages")
    try:
        snapshot = prices.fetch_snapshot(model_ids)
    except prices.PricingLayoutError as err:
        print("OpenAI's pages no longer match the expected layout; the snapshot was not changed:")
        for problem in err.problems:
            print(f"  - {problem}")
        return 1
    except prices.PricingFetchError as err:
        print(f"could not fetch the pages, the snapshot was not changed: {err}")
        return 1

    old = prices.load_saved(SNAPSHOT.parent) or {"models": {}}
    diff = prices.changes(old, snapshot)
    prices.save(snapshot, SNAPSHOT)
    priced = sum(1 for m in snapshot["models"].values() if m["prices"])
    print(f"wrote {SNAPSHOT}")
    print(f"fetched at {snapshot['fetched_at']}: {priced} models with prices, {len(diff)} changes")
    for line in diff:
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
