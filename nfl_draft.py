from __future__ import annotations

from argparse import ArgumentParser
import csv
from dataclasses import dataclass
from functools import lru_cache
from io import StringIO
from random import Random
from urllib.error import URLError
from urllib.request import urlopen
from typing import Iterable, List


NFL_TEAMS = [
    "Arizona Cardinals",
    "Atlanta Falcons",
    "Baltimore Ravens",
    "Buffalo Bills",
    "Carolina Panthers",
    "Chicago Bears",
    "Cincinnati Bengals",
    "Cleveland Browns",
    "Dallas Cowboys",
    "Denver Broncos",
    "Detroit Lions",
    "Green Bay Packers",
    "Houston Texans",
    "Indianapolis Colts",
    "Jacksonville Jaguars",
    "Kansas City Chiefs",
    "Las Vegas Raiders",
    "Los Angeles Chargers",
    "Los Angeles Rams",
    "Miami Dolphins",
    "Minnesota Vikings",
    "New England Patriots",
    "New Orleans Saints",
    "New York Giants",
    "New York Jets",
    "Philadelphia Eagles",
    "Pittsburgh Steelers",
    "San Francisco 49ers",
    "Seattle Seahawks",
    "Tampa Bay Buccaneers",
    "Tennessee Titans",
    "Washington Commanders",
]


@dataclass(frozen=True)
class DraftPick:
    year: int
    overall_pick: int
    round_number: int
    round_pick: int
    team: str
    player: str


def _default_prospects(total_players: int) -> List[str]:
    return [f"Prospect {index:03d}" for index in range(1, total_players + 1)]


DEFAULT_PROSPECT_SOURCE_URL = (
    "https://raw.githubusercontent.com/cwecht15/Mock-Draft-Database/"
    "7d86e94057b0f1b200791d4f40b898575efe7f0f/"
    "data/processed/2026/teams__player_trends.csv"
)
DEFAULT_PROSPECT_SOURCE_TIMEOUT_SECONDS = 5.0


def _load_prospects_from_csv_text(csv_text: str) -> List[str]:
    rows = csv.DictReader(StringIO(csv_text))
    prospects = [player_name for row in rows if (player_name := row.get("player_name", "").strip())]
    return prospects


def _fetch_real_2026_prospects() -> List[str]:
    try:
        with urlopen(DEFAULT_PROSPECT_SOURCE_URL, timeout=DEFAULT_PROSPECT_SOURCE_TIMEOUT_SECONDS) as response:
            csv_text = response.read().decode("utf-8")
        prospects = _load_prospects_from_csv_text(csv_text)
        if prospects:
            return prospects
    except (OSError, URLError, ValueError):
        pass
    return []


@lru_cache(maxsize=1)
def get_real_2026_prospects() -> List[str]:
    return _fetch_real_2026_prospects()


def simulate_draft(
    *,
    year: int = 2026,
    rounds: int = 7,
    teams: Iterable[str] = NFL_TEAMS,
    random_seed: int = 2026,
    prospects: Iterable[str] | None = None,
) -> List[DraftPick]:
    team_order = list(teams)
    if not team_order:
        raise ValueError("At least one team is required to simulate a draft.")
    if rounds <= 0:
        raise ValueError("Rounds must be greater than zero.")

    total_picks = rounds * len(team_order)
    real_prospects = list(prospects) if prospects is not None else get_real_2026_prospects()
    randomized_prospects = real_prospects[:total_picks]
    if len(randomized_prospects) < total_picks:
        randomized_prospects.extend(_default_prospects(total_picks - len(randomized_prospects)))
    Random(random_seed).shuffle(randomized_prospects)

    picks: List[DraftPick] = []
    overall_pick = 1
    for round_number in range(1, rounds + 1):
        for round_pick, team in enumerate(team_order, start=1):
            picks.append(
                DraftPick(
                    year=year,
                    overall_pick=overall_pick,
                    round_number=round_number,
                    round_pick=round_pick,
                    team=team,
                    player=randomized_prospects[overall_pick - 1],
                )
            )
            overall_pick += 1
    return picks


def get_team_picks(picks: Iterable[DraftPick], team_name: str) -> List[DraftPick]:
    normalized = team_name.strip().casefold()
    return [pick for pick in picks if pick.team.casefold() == normalized]


def _parse_args() -> ArgumentParser:
    parser = ArgumentParser(description="Simulate and query the 2026 NFL Draft.")
    parser.add_argument(
        "--team",
        type=str,
        help="Optional team name to show only that team's draft picks.",
    )
    return parser


def main() -> None:
    parser = _parse_args()
    args = parser.parse_args()

    picks = simulate_draft()
    selected_picks = picks if not args.team else get_team_picks(picks, args.team)

    if args.team and not selected_picks:
        available_teams = ", ".join(NFL_TEAMS)
        raise SystemExit(f"Unknown team '{args.team}'. Valid teams: {available_teams}")

    for pick in selected_picks:
        print(
            f"#{pick.overall_pick:03d} | Round {pick.round_number} Pick {pick.round_pick:02d} | "
            f"{pick.team} -> {pick.player}"
        )


if __name__ == "__main__":
    main()
