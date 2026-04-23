from __future__ import annotations

from argparse import ArgumentParser
import csv
from dataclasses import dataclass
from functools import lru_cache
from io import StringIO
import json
import pathlib
from random import Random
from urllib.error import URLError
from urllib.request import urlopen
from typing import Callable, Dict, Iterable, List, Optional, Tuple, Union


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


# ---------------------------------------------------------------------------
# Position normalisation – maps Drafttek-specific codes to canonical groups
# used in team needs lists.
# ---------------------------------------------------------------------------

POSITION_GROUPS: Dict[str, str] = {
    # Defensive line variants → DL
    "DL1T": "DL",
    "DL3T": "DL",
    "DL5T": "DL",
    # Outside linebacker treated as edge rusher
    "OLB": "EDGE",
    # Nickel corner → CB
    "CBN": "CB",
    # Slot receiver → WR
    "WRS": "WR",
}


def _canonical_position(raw_pos: str) -> str:
    """Return the canonical positional group for a raw Drafttek position code.

    Positions not listed in :data:`POSITION_GROUPS` map to themselves.
    """
    return POSITION_GROUPS.get(raw_pos, raw_pos)


# ---------------------------------------------------------------------------
# Team needs data – loaded once from the bundled JSON file
# ---------------------------------------------------------------------------

TEAM_NEEDS_PATH = pathlib.Path(__file__).parent / "team_needs_2026.json"


@lru_cache(maxsize=1)
def load_team_needs() -> Dict[str, List[str]]:
    """Return 2026 positional needs per team, loaded from *team_needs_2026.json*.

    Each value is an ordered list of canonical position codes (most critical
    first).  Returns an empty dict when the file is missing or malformed.
    """
    try:
        data = json.loads(TEAM_NEEDS_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): [str(v) for v in vs] for k, vs in data.items()}
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return {}


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

# ---------------------------------------------------------------------------
# Draft-order fetch – nflverse releases CSV (same team abbreviations as
# NFL_TEAM_ABBREVIATIONS; populated after each draft concludes)
# ---------------------------------------------------------------------------

NFLVERSE_DRAFT_PICKS_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "draft_picks/draft_picks.csv"
)
NFLVERSE_DRAFT_PICKS_TIMEOUT_SECONDS = 10.0

# Round 1 pick order for the 2026 NFL Draft.
# Picks 1–24 are the officially announced order; picks 25–32 are estimated
# from 2025 season standings and available trade information.
_DRAFT_ORDER_2026_ROUND_1: List[str] = [
    "Las Vegas Raiders",       # 1
    "New York Jets",           # 2
    "Arizona Cardinals",       # 3
    "Tennessee Titans",        # 4
    "New York Giants",         # 5
    "Cleveland Browns",        # 6
    "Washington Commanders",   # 7
    "New Orleans Saints",      # 8
    "Kansas City Chiefs",      # 9
    "Cincinnati Bengals",      # 10
    "Miami Dolphins",          # 11
    "Dallas Cowboys",          # 12
    "Los Angeles Rams",        # 13 (from Atlanta Falcons via trade)
    "Baltimore Ravens",        # 14
    "Tampa Bay Buccaneers",    # 15
    "New York Jets",           # 16 (from Indianapolis Colts via trade)
    "Detroit Lions",           # 17
    "Minnesota Vikings",       # 18
    "Carolina Panthers",       # 19
    "Dallas Cowboys",          # 20 (from Green Bay Packers via trade)
    "Pittsburgh Steelers",     # 21
    "Los Angeles Chargers",    # 22
    "Philadelphia Eagles",     # 23
    "Cleveland Browns",        # 24 (from Jacksonville Jaguars via trade)
    "New England Patriots",    # 25 (estimated)
    "Chicago Bears",           # 26 (estimated)
    "Denver Broncos",          # 27 (estimated)
    "Houston Texans",          # 28 (estimated)
    "Los Angeles Rams",        # 29 (estimated – original pick; earlier pick acquired via trade)
    "San Francisco 49ers",     # 30 (estimated)
    "Seattle Seahawks",        # 31 (estimated)
    "Buffalo Bills",           # 32 (estimated)
]

# Rounds 2–7 base order: all 32 teams in approximate inverse-standings order.
# Teams that traded away their Round 1 pick still hold later-round picks.
_DRAFT_ORDER_2026_ROUNDS_2_TO_7: List[str] = [
    "Las Vegas Raiders",
    "New York Jets",
    "Arizona Cardinals",
    "Tennessee Titans",
    "New York Giants",
    "Cleveland Browns",
    "Jacksonville Jaguars",     # traded Round 1 pick; still holds later picks
    "Washington Commanders",
    "New Orleans Saints",
    "Atlanta Falcons",          # traded Round 1 pick; still holds later picks
    "Kansas City Chiefs",
    "Cincinnati Bengals",
    "Miami Dolphins",
    "Indianapolis Colts",       # traded Round 1 pick; still holds later picks
    "Dallas Cowboys",
    "Los Angeles Rams",
    "Baltimore Ravens",
    "Tampa Bay Buccaneers",
    "Detroit Lions",
    "Minnesota Vikings",
    "Carolina Panthers",
    "Green Bay Packers",        # traded Round 1 pick; still holds later picks
    "Pittsburgh Steelers",
    "Los Angeles Chargers",
    "Philadelphia Eagles",
    "New England Patriots",
    "Chicago Bears",
    "Denver Broncos",
    "Houston Texans",
    "San Francisco 49ers",
    "Seattle Seahawks",
    "Buffalo Bills",
]


def _hardcoded_draft_order_2026() -> List[Tuple[int, str]]:
    """Return a best-effort 2026 NFL Draft pick sequence as (round, team) pairs.

    Round 1 picks 1–24 are taken from the officially announced order.
    Picks 25–32 of Round 1 and all of Rounds 2–7 are estimated from 2025
    season standings and may not perfectly reflect actual trade activity.
    """
    sequence: List[Tuple[int, str]] = []
    for team in _DRAFT_ORDER_2026_ROUND_1:
        sequence.append((1, team))
    for round_number in range(2, 8):
        for team in _DRAFT_ORDER_2026_ROUNDS_2_TO_7:
            sequence.append((round_number, team))
    return sequence


def _fetch_draft_order_from_nflverse(year: int) -> List[Tuple[int, str]]:
    """Fetch the full draft pick order for *year* from the nflverse data release.

    Returns a list of ``(round_number, team_name)`` tuples sorted by overall
    pick number.  Returns an empty list when the year is not yet available or
    the fetch fails.
    """
    try:
        with urlopen(NFLVERSE_DRAFT_PICKS_URL, timeout=NFLVERSE_DRAFT_PICKS_TIMEOUT_SECONDS) as response:
            csv_text = response.read().decode("utf-8")
    except (OSError, URLError, ValueError):
        return []

    try:
        rows = list(csv.DictReader(StringIO(csv_text)))
    except Exception:
        return []

    year_str = str(year)
    year_rows = [row for row in rows if row.get("season") == year_str]
    if not year_rows:
        return []

    try:
        year_rows.sort(key=lambda r: int(r.get("pick", 0)))
    except (ValueError, TypeError):
        return []

    sequence: List[Tuple[int, str]] = []
    for row in year_rows:
        try:
            round_number = int(row.get("round", 0))
        except (ValueError, TypeError):
            continue
        team_abbr = str(row.get("team", "")).strip()
        team_name = NFL_TEAM_ABBREVIATIONS.get(team_abbr, team_abbr)
        if round_number > 0 and team_name:
            sequence.append((round_number, team_name))
    return sequence


@lru_cache(maxsize=8)
def get_draft_order(year: int) -> List[Tuple[int, str]]:
    """Return the full draft pick order for *year* as ``(round, team)`` pairs.

    Tries the nflverse data release first (accurate post-draft data).  Falls
    back to a hardcoded 2026 order (Round 1 picks 1–24 are exact; the rest are
    estimated) when nflverse data is not yet available.  For years other than
    2026, returns an empty list when the remote fetch fails.
    """
    remote = _fetch_draft_order_from_nflverse(year)
    if remote:
        return remote
    if year == 2026:
        return _hardcoded_draft_order_2026()
    return []


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


def _pick_by_need(
    pool: List[ProspectInfo],
    team: str,
    team_needs: Dict[str, List[str]],
) -> int:
    """Return the index of the best prospect in *pool* for *team*'s needs.

    Scans the team's positional needs in priority order and returns the index
    of the highest-ranked available prospect (lowest index = highest rank) that
    matches each need in turn.  Falls back to index 0 (Best Player Available)
    when no prospect matches any listed need.
    """
    needs = team_needs.get(team, [])
    for need in needs:
        for idx, prospect in enumerate(pool):
            if _canonical_position(prospect.position) == need:
                return idx
    return 0  # BPA fallback


def simulate_draft(
    *,
    year: int = 2026,
    rounds: int = 7,
    teams: Iterable[str] = NFL_TEAMS,
    pick_sequence: Optional[List[Tuple[int, str]]] = None,
    random_seed: int = 2026,
    prospects: Union[Iterable[Union[str, ProspectInfo]], None] = None,
    use_team_needs: bool = False,
) -> List[DraftPick]:
    """Simulate a draft and return a list of :class:`DraftPick` objects.

    *pick_sequence* is the preferred way to control team order.  It should be a
    list of ``(round_number, team_name)`` pairs covering every pick in the draft
    (e.g. from :func:`get_draft_order`).  When provided, *rounds* and *teams*
    are ignored for ordering purposes.

    When *pick_sequence* is ``None`` the draft is simulated by cycling through
    *teams* once per round for *rounds* rounds (the legacy behaviour).

    *prospects* may contain plain name strings or :class:`ProspectInfo` objects.
    When *prospects* is ``None`` the fallback chain is applied:

    1. Local Drafttek CSV (``drafttek_2026_top600_with_bio.csv``).
    2. Remote mock-draft CSV (cwecht15/Mock-Draft-Database on GitHub).
    3. Generated placeholder names.

    When *use_team_needs* is ``True`` the prospect pool is kept in rank order
    and each team selects the highest-ranked available player that fits its top
    positional need (greedy need-based selection).  When no need is matched the
    best available player is chosen instead.  When ``False`` (default) the
    original random-shuffle behaviour is used.
    """
    if pick_sequence is not None:
        total_picks = len(pick_sequence)
    else:
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

    pool = prospect_infos[:total_picks]
    if len(pool) < total_picks:
        pool = pool + [
            ProspectInfo(name=p) for p in _default_prospects(total_picks - len(pool))
        ]

    # Build a callable that returns the next prospect for a given picking team.
    selector: Callable[[str], ProspectInfo]
    if use_team_needs:
        # Need-based mode: keep pool in rank order; select greedily by need.
        team_needs_map = load_team_needs()
        mutable_pool = list(pool)

        class _NeedsSelector:
            def __call__(self, team: str) -> ProspectInfo:
                idx = _pick_by_need(mutable_pool, team, team_needs_map)
                return mutable_pool.pop(idx)

        selector = _NeedsSelector()
    else:
        # Random mode (original behaviour): shuffle then assign by index.
        randomized = list(pool)
        Random(random_seed).shuffle(randomized)
        pick_iter = iter(randomized)

        class _RandomSelector:  # type: ignore[no-redef]
            def __call__(self, team: str) -> ProspectInfo:
                return next(pick_iter)

        selector = _RandomSelector()

    picks: List[DraftPick] = []
    if pick_sequence is not None:
        picks_per_round: dict[int, int] = {}
        for overall_pick, (round_number, team) in enumerate(pick_sequence, start=1):
            picks_per_round[round_number] = picks_per_round.get(round_number, 0) + 1
            info = selector(team)
            picks.append(
                DraftPick(
                    year=year,
                    overall_pick=overall_pick,
                    round_number=round_number,
                    round_pick=picks_per_round[round_number],
                    team=team,
                    player=info.name,
                    position=info.position,
                    college=info.college,
                    bio_url=info.bio_url,
                )
            )
    else:
        overall_pick = 1
        for round_number in range(1, rounds + 1):
            for round_pick, team in enumerate(team_order, start=1):
                info = selector(team)
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
    parser.add_argument(
        "--needs",
        action="store_true",
        default=False,
        help="Use need-based player selection instead of random assignment.",
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
        draft_order = get_draft_order(2026)
        picks = simulate_draft(pick_sequence=draft_order or None, use_team_needs=args.needs)
        mode = "needs-based" if args.needs else "random"
        if draft_order:
            remote = _fetch_draft_order_from_nflverse(2026)
            source = (
                f"simulation ({mode}) with nflverse draft order"
                if remote
                else f"simulation ({mode}) with hardcoded 2026 draft order (picks 1–24 official, rest estimated)"
            )
        else:
            source = f"simulation ({mode}) (nfl_data_py data not yet available)"

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
