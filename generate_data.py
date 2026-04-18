#!/usr/bin/env python3
"""Generate docs/draft_data.json for GitHub Pages.

Run this script (or let the GitHub Actions workflow run it) to refresh the
JSON data file consumed by the static web UI in /docs.
"""
from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone

from nfl_draft import import_actual_draft_picks, get_draft_order, simulate_draft, _fetch_draft_order_from_nflverse

DOCS_DIR = pathlib.Path(__file__).parent / "docs"


def build_data() -> dict:
    actual_picks = import_actual_draft_picks(2026)
    if actual_picks:
        picks = actual_picks
        source = "nfl_data_py"
    else:
        draft_order = get_draft_order(2026)
        picks = simulate_draft(pick_sequence=draft_order or None)
        if draft_order:
            remote = _fetch_draft_order_from_nflverse(2026)
            source = (
                "simulation with nflverse draft order"
                if remote
                else "simulation with hardcoded 2026 draft order (picks 1–24 official, rest estimated)"
            )
        else:
            source = "simulation"

    return {
        "source": source,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "picks": [
            {
                "overall_pick": pick.overall_pick,
                "round_number": pick.round_number,
                "round_pick": pick.round_pick,
                "team": pick.team,
                "player": pick.player,
                "position": pick.position,
                "college": pick.college,
                "bio_url": pick.bio_url,
            }
            for pick in picks
        ],
    }


def main() -> None:
    data = build_data()
    output_path = DOCS_DIR / "draft_data.json"
    output_path.write_text(json.dumps(data, indent=2) + "\n")
    pick_count = len(data["picks"])
    print(f"Wrote {pick_count} picks to {output_path} (source: {data['source']})")


if __name__ == "__main__":
    main()
