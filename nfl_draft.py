from __future__ import annotations

from argparse import ArgumentParser
import csv
from dataclasses import dataclass
from functools import lru_cache
from io import StringIO
import pathlib
from random import Random
from urllib.error import URLError
from urllib.request import urlopen
from typing import Iterable, List, Union


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

# Maps nfl_data_py team abbreviations to full team names used throughout this project.
NFL_TEAM_ABBREVIATIONS: dict[str, str] = {
    "ARI": "Arizona Cardinals",
    "ATL": "Atlanta Falcons",
    "BAL": "Baltimore Ravens",
    "BUF": "Buffalo Bills",
    "CAR": "Carolina Panthers",
    "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals",
    "CLE": "Cleveland Browns",
    "DAL": "Dallas Cowboys",
    "DEN": "Denver Broncos",
    "DET": "Detroit Lions",
    "GNB": "Green Bay Packers",
    "HOU": "Houston Texans",
    "IND": "Indianapolis Colts",
    "JAX": "Jacksonville Jaguars",
    "KAN": "Kansas City Chiefs",
    "LAC": "Los Angeles Chargers",
    "LAR": "Los Angeles Rams",
    "LVR": "Las Vegas Raiders",
    "MIA": "Miami Dolphins",
    "MIN": "Minnesota Vikings",
    "NOR": "New Orleans Saints",
    "NWE": "New England Patriots",
    "NYG": "New York Giants",
    "NYJ": "New York Jets",
    "PHI": "Philadelphia Eagles",
    "PIT": "Pittsburgh Steelers",
    "SEA": "Seattle Seahawks",
    "SFO": "San Francisco 49ers",
    "TAM": "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans",
    "WAS": "Washington Commanders",
}


@dataclass(frozen=True)
class ProspectInfo:
    """Prospect metadata loaded from the Drafttek rankings CSV."""

    name: str
    position: str = ""
    college: str = ""
    bio_url: str = ""


@dataclass(frozen=True)
class DraftPick:
    year: int
    overall_pick: int
    round_number: int
    round_pick: int
    team: str
    player: str
    position: str = ""
    college: str = ""
    bio_url: str = ""


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
    prospects: List[str] = []
    for row in rows:
        player_name = row.get("player_name", "").strip()
        if player_name:
            prospects.append(player_name)
    return prospects


def _fetch_real_2026_prospects() -> List[str]:
    try:
        with urlopen(DEFAULT_PROSPECT_SOURCE_URL, timeout=DEFAULT_PROSPECT_SOURCE_TIMEOUT_SECONDS) as response:
            csv_text = response.read().decode("utf-8")
        prospects = _load_prospects_from_csv_text(csv_text)
        if prospects:
            return prospects
    except (OSError, URLError, ValueError):
        # ValueError can occur while decoding invalid response bytes or parsing malformed CSV.
        pass
    return []


@lru_cache(maxsize=1)
def get_real_2026_prospects() -> List[str]:
    return _fetch_real_2026_prospects()


# ---------------------------------------------------------------------------
# Drafttek prospect loader – primary local source for simulation
# ---------------------------------------------------------------------------

DRAFTTEK_CSV_PATH = pathlib.Path(__file__).parent / "drafttek_2026_top600_with_bio.csv"


def _load_drafttek_prospects_from_csv_text(csv_text: str) -> List[ProspectInfo]:
    """Parse a Drafttek rankings CSV and return a list of :class:`ProspectInfo`.

    The CSV is expected to have at minimum a ``Prospect`` column.  ``POS``,
    ``College``, and ``Bio_URL`` columns are used when present.  Rows with a
    blank ``Prospect`` value are silently skipped.
    """
    prospects: List[ProspectInfo] = []
    for row in csv.DictReader(StringIO(csv_text)):
        name = row.get("Prospect", "").strip()
        if not name:
            continue
        prospects.append(
            ProspectInfo(
                name=name,
                position=row.get("POS", "").strip(),
                college=row.get("College", "").strip(),
                bio_url=(row.get("Bio_URL") or "").strip(),
            )
        )
    return prospects


def _load_drafttek_prospects() -> List[ProspectInfo]:
    """Load prospects from the local Drafttek CSV file.

    Returns an empty list if the file is missing or unreadable.
    """
    try:
        csv_text = DRAFTTEK_CSV_PATH.read_text(encoding="utf-8")
        prospects = _load_drafttek_prospects_from_csv_text(csv_text)
        if prospects:
            return prospects
    except OSError:
        pass
    return []


@lru_cache(maxsize=1)
def get_drafttek_2026_prospects() -> List[ProspectInfo]:
    """Return cached Drafttek 2026 top-600 prospects (primary simulation source)."""
    return _load_drafttek_prospects()


def _fetch_actual_draft_picks(year: int) -> List[DraftPick]:
    """Fetch completed draft picks from nfl_data_py for *year*.

    Returns an empty list when:
    - ``nfl_data_py`` is not installed, or
    - no data is available yet for the requested year (e.g. pre-draft).
    """
    try:
        import nfl_data_py as nfl  # optional heavy dependency
    except ModuleNotFoundError:
        return []

    try:
        df = nfl.import_draft_picks([year])
    except Exception:
        return []

    if df is None or df.empty:
        return []

    picks: List[DraftPick] = []
    # Compute the pick number within each round from the global pick order.
    round_pick_counter: dict[int, int] = {}
    for row in df.sort_values("pick").itertuples(index=False):
        round_number = int(row.round)
        round_pick_counter[round_number] = round_pick_counter.get(round_number, 0) + 1

        team_abbr = str(getattr(row, "team", ""))
        team_name = NFL_TEAM_ABBREVIATIONS.get(team_abbr, team_abbr)

        player_name = str(getattr(row, "pfr_player_name", "")).strip()
        if not player_name:
            player_name = f"Player {int(row.pick)}"

        picks.append(
            DraftPick(
                year=int(row.season),
                overall_pick=int(row.pick),
                round_number=round_number,
                round_pick=round_pick_counter[round_number],
                team=team_name,
                player=player_name,
            )
        )

    return picks


@lru_cache(maxsize=8)
def import_actual_draft_picks(year: int) -> List[DraftPick]:
    """Return real, completed draft picks for *year* sourced from nfl_data_py.

    Returns an empty list when the data is not yet available (e.g. the draft
    has not taken place) or when ``nfl_data_py`` is not installed.
    """
    return _fetch_actual_draft_picks(year)


def simulate_draft(
    *,
    year: int = 2026,
    rounds: int = 7,
    teams: Iterable[str] = NFL_TEAMS,
    random_seed: int = 2026,
    prospects: Union[Iterable[Union[str, ProspectInfo]], None] = None,
) -> List[DraftPick]:
    """Simulate a draft and return a list of :class:`DraftPick` objects.

    *prospects* may contain plain name strings or :class:`ProspectInfo` objects.
    When *prospects* is ``None`` the fallback chain is applied:

    1. Local Drafttek CSV (``drafttek_2026_top600_with_bio.csv``).
    2. Remote mock-draft CSV (cwecht15/Mock-Draft-Database on GitHub).
    3. Generated placeholder names.
    """
    team_order = list(teams)
    if not team_order:
        raise ValueError("At least one team is required to simulate a draft.")
    if rounds <= 0:
        raise ValueError("Rounds must be greater than zero.")

    total_picks = rounds * len(team_order)

    # Build a normalized list of ProspectInfo regardless of input type.
    if prospects is not None:
        prospect_infos: List[ProspectInfo] = [
            p if isinstance(p, ProspectInfo) else ProspectInfo(name=str(p))
            for p in prospects
        ]
    else:
        # Fallback chain: local Drafttek → remote mock-draft CSV → placeholders
        prospect_infos = get_drafttek_2026_prospects()
        if not prospect_infos:
            prospect_infos = [ProspectInfo(name=n) for n in get_real_2026_prospects()]

    randomized = prospect_infos[:total_picks]
    if len(randomized) < total_picks:
        randomized = randomized + [
            ProspectInfo(name=p) for p in _default_prospects(total_picks - len(randomized))
        ]
    Random(random_seed).shuffle(randomized)

    picks: List[DraftPick] = []
    overall_pick = 1
    for round_number in range(1, rounds + 1):
        for round_pick, team in enumerate(team_order, start=1):
            info = randomized[overall_pick - 1]
            picks.append(
                DraftPick(
                    year=year,
                    overall_pick=overall_pick,
                    round_number=round_number,
                    round_pick=round_pick,
                    team=team,
                    player=info.name,
                    position=info.position,
                    college=info.college,
                    bio_url=info.bio_url,
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

    # Prefer actual completed draft picks from nfl_data_py; fall back to simulation.
    actual_picks = import_actual_draft_picks(2026)
    if actual_picks:
        picks = actual_picks
        source = "nfl_data_py"
    else:
        picks = simulate_draft()
        source = "simulation (nfl_data_py data not yet available)"

    selected_picks = picks if not args.team else get_team_picks(picks, args.team)

    if args.team and not selected_picks:
        available_teams = ", ".join(NFL_TEAMS)
        raise SystemExit(f"Unknown team '{args.team}'. Valid teams: {available_teams}")

    print(f"# Source: {source}")
    for pick in selected_picks:
        print(
            f"#{pick.overall_pick:03d} | Round {pick.round_number} Pick {pick.round_pick:02d} | "
            f"{pick.team} -> {pick.player}"
        )


if __name__ == "__main__":
    main()
