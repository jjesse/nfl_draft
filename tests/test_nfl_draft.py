import csv
import io
import unittest
from collections import Counter
from unittest.mock import MagicMock, Mock, patch

from nfl_draft import (
    NFL_TEAM_ABBREVIATIONS,
    ProspectInfo,
    _DRAFT_ORDER_2026_ROUND_1,
    _DRAFT_ORDER_2026_ROUNDS_2_TO_7,
    _fetch_actual_draft_picks,
    _fetch_draft_order_from_nflverse,
    _fetch_real_2026_prospects,
    _hardcoded_draft_order_2026,
    _load_drafttek_prospects_from_csv_text,
    _load_prospects_from_csv_text,
    get_draft_order,
    get_drafttek_2026_prospects,
    get_team_picks,
    import_actual_draft_picks,
    simulate_draft,
)


def _test_prospects(count: int = 224) -> list[str]:
    return [f"Test Player {index:03d}" for index in range(1, count + 1)]


class DraftSimulationTests(unittest.TestCase):
    def test_simulate_draft_creates_224_picks(self) -> None:
        picks = simulate_draft(prospects=_test_prospects())
        self.assertEqual(224, len(picks))
        self.assertEqual(list(range(1, 225)), [pick.overall_pick for pick in picks])

    def test_each_team_gets_seven_picks(self) -> None:
        picks = simulate_draft(prospects=_test_prospects())
        by_team = Counter(pick.team for pick in picks)
        self.assertEqual(32, len(by_team))
        self.assertTrue(all(count == 7 for count in by_team.values()))

    def test_can_query_team_picks(self) -> None:
        picks = simulate_draft(prospects=_test_prospects())
        dallas_picks = get_team_picks(picks, "Dallas Cowboys")
        self.assertEqual(7, len(dallas_picks))
        self.assertTrue(all(pick.team == "Dallas Cowboys" for pick in dallas_picks))

    @patch("nfl_draft.urlopen")
    def test_real_prospects_are_loaded_from_csv_source(self, mock_urlopen: Mock) -> None:
        mock_response = Mock()
        mock_response.read.return_value = (
            b"player_name,player_position\n"
            b"Caleb Downs,S\n"
            b"Jeremiyah Love,RB\n"
        )
        mock_urlopen.return_value.__enter__.return_value = mock_response

        prospects = _fetch_real_2026_prospects()

        self.assertEqual(["Caleb Downs", "Jeremiyah Love"], prospects)

    def test_load_prospects_from_csv_text_filters_blank_names(self) -> None:
        csv_text = (
            "player_name,player_position\n"
            "Caleb Downs,S\n"
            ",CB\n"
            "Jeremiyah Love,RB\n"
        )
        self.assertEqual(
            ["Caleb Downs", "Jeremiyah Love"],
            _load_prospects_from_csv_text(csv_text),
        )


class TeamAbbreviationTests(unittest.TestCase):
    def test_all_32_teams_are_mapped(self) -> None:
        self.assertEqual(32, len(NFL_TEAM_ABBREVIATIONS))

    def test_known_abbreviations_resolve_correctly(self) -> None:
        self.assertEqual("Kansas City Chiefs", NFL_TEAM_ABBREVIATIONS["KAN"])
        self.assertEqual("San Francisco 49ers", NFL_TEAM_ABBREVIATIONS["SFO"])
        self.assertEqual("Green Bay Packers", NFL_TEAM_ABBREVIATIONS["GNB"])
        self.assertEqual("New England Patriots", NFL_TEAM_ABBREVIATIONS["NWE"])
        self.assertEqual("Las Vegas Raiders", NFL_TEAM_ABBREVIATIONS["LVR"])

    def test_all_mapped_names_are_in_nfl_teams(self) -> None:
        from nfl_draft import NFL_TEAMS

        for abbr, full_name in NFL_TEAM_ABBREVIATIONS.items():
            self.assertIn(full_name, NFL_TEAMS, msg=f"Full name for {abbr!r} not in NFL_TEAMS")


class FetchActualDraftPicksTests(unittest.TestCase):
    def test_returns_empty_list_when_nfl_data_py_not_installed(self) -> None:
        import builtins
        real_import = builtins.__import__

        def _block_nfl_data_py(name, *args, **kwargs):
            if name == "nfl_data_py":
                raise ModuleNotFoundError("nfl_data_py not installed")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=_block_nfl_data_py):
            result = _fetch_actual_draft_picks(2026)

        self.assertEqual([], result)

    def test_returns_empty_list_when_dataframe_is_empty(self) -> None:
        import pandas as pd

        mock_nfl = MagicMock()
        mock_nfl.import_draft_picks.return_value = pd.DataFrame(
            columns=["season", "round", "pick", "team", "pfr_player_name"]
        )

        with patch.dict("sys.modules", {"nfl_data_py": mock_nfl}):
            result = _fetch_actual_draft_picks(2099)

        self.assertEqual([], result)

    def test_converts_dataframe_rows_to_draft_picks(self) -> None:
        import pandas as pd

        rows = [
            {"season": 2025, "round": 1, "pick": 1, "team": "TEN", "pfr_player_name": "Cam Ward"},
            {"season": 2025, "round": 1, "pick": 2, "team": "JAX", "pfr_player_name": "Travis Hunter"},
            {"season": 2025, "round": 2, "pick": 33, "team": "CLE", "pfr_player_name": "Carson Schwesinger"},
        ]
        mock_nfl = MagicMock()
        mock_nfl.import_draft_picks.return_value = pd.DataFrame(rows)

        with patch.dict("sys.modules", {"nfl_data_py": mock_nfl}):
            result = _fetch_actual_draft_picks(2025)

        self.assertEqual(3, len(result))

        first = result[0]
        self.assertEqual(2025, first.year)
        self.assertEqual(1, first.overall_pick)
        self.assertEqual(1, first.round_number)
        self.assertEqual(1, first.round_pick)
        self.assertEqual("Tennessee Titans", first.team)
        self.assertEqual("Cam Ward", first.player)

        third = result[2]
        self.assertEqual(33, third.overall_pick)
        self.assertEqual(2, third.round_number)
        self.assertEqual(1, third.round_pick)  # first pick of round 2
        self.assertEqual("Cleveland Browns", third.team)

    def test_round_pick_increments_within_each_round(self) -> None:
        import pandas as pd

        rows = [
            {"season": 2025, "round": 2, "pick": 33, "team": "CLE", "pfr_player_name": "Player A"},
            {"season": 2025, "round": 2, "pick": 34, "team": "HOU", "pfr_player_name": "Player B"},
            {"season": 2025, "round": 2, "pick": 35, "team": "SEA", "pfr_player_name": "Player C"},
        ]
        mock_nfl = MagicMock()
        mock_nfl.import_draft_picks.return_value = pd.DataFrame(rows)

        with patch.dict("sys.modules", {"nfl_data_py": mock_nfl}):
            result = _fetch_actual_draft_picks(2025)

        self.assertEqual([1, 2, 3], [p.round_pick for p in result])

    def test_missing_player_name_uses_fallback(self) -> None:
        import pandas as pd

        rows = [
            {"season": 2025, "round": 1, "pick": 5, "team": "ARI", "pfr_player_name": ""},
        ]
        mock_nfl = MagicMock()
        mock_nfl.import_draft_picks.return_value = pd.DataFrame(rows)

        with patch.dict("sys.modules", {"nfl_data_py": mock_nfl}):
            result = _fetch_actual_draft_picks(2025)

        self.assertEqual("Player 5", result[0].player)


class ImportActualDraftPicksTests(unittest.TestCase):
    def test_import_actual_draft_picks_is_cached(self) -> None:
        import pandas as pd

        mock_nfl = MagicMock()
        mock_nfl.import_draft_picks.return_value = pd.DataFrame(
            columns=["season", "round", "pick", "team", "pfr_player_name"]
        )

        # Clear lru_cache so we get a clean call count
        import_actual_draft_picks.cache_clear()

        with patch.dict("sys.modules", {"nfl_data_py": mock_nfl}):
            import_actual_draft_picks(2099)
            import_actual_draft_picks(2099)

        self.assertEqual(1, mock_nfl.import_draft_picks.call_count)

        # Restore cache state
        import_actual_draft_picks.cache_clear()


class DrafttekProspectLoaderTests(unittest.TestCase):
    """Tests for the Drafttek CSV prospect loader."""

    _SAMPLE_CSV = (
        "Rank,CNG,Prospect,College,POS,Ht,Wt,CLS,Bio_URL\n"
        "1,--,Fernando Mendoza,Indiana,QB,6'5\",236,RJR,https://iuhoosiers.com/roster/fernando-mendoza\n"
        "2,--,Arvell Reese,Ohio State,EDGE,6'4\",241,JR,https://ohiostatebuckeyes.com/roster/arvell-reese\n"
        "3,--,,Notre Dame,RB,6'0\",212,JR,\n"
    )

    def test_parses_prospect_name_position_college_bio_url(self) -> None:
        prospects = _load_drafttek_prospects_from_csv_text(self._SAMPLE_CSV)
        self.assertEqual(2, len(prospects))
        first = prospects[0]
        self.assertEqual("Fernando Mendoza", first.name)
        self.assertEqual("QB", first.position)
        self.assertEqual("Indiana", first.college)
        self.assertEqual("https://iuhoosiers.com/roster/fernando-mendoza", first.bio_url)

    def test_filters_rows_with_blank_prospect_name(self) -> None:
        prospects = _load_drafttek_prospects_from_csv_text(self._SAMPLE_CSV)
        names = [p.name for p in prospects]
        self.assertNotIn("", names)
        self.assertEqual(2, len(prospects))

    def test_returns_prospect_info_instances(self) -> None:
        prospects = _load_drafttek_prospects_from_csv_text(self._SAMPLE_CSV)
        self.assertTrue(all(isinstance(p, ProspectInfo) for p in prospects))

    def test_missing_bio_url_defaults_to_empty_string(self) -> None:
        csv_text = (
            "Rank,CNG,Prospect,College,POS,Ht,Wt,CLS,Bio_URL\n"
            "1,--,Test Player,State U,WR,6'0\",190,SR,\n"
        )
        prospects = _load_drafttek_prospects_from_csv_text(csv_text)
        self.assertEqual("", prospects[0].bio_url)

    def test_simulate_draft_uses_drafttek_prospects_as_primary_fallback(self) -> None:
        drafttek_infos = [ProspectInfo(name=f"Prospect {i}", position="WR", college="State U") for i in range(1, 300)]
        with patch("nfl_draft.get_drafttek_2026_prospects", return_value=drafttek_infos):
            picks = simulate_draft()
        self.assertEqual(224, len(picks))
        # All players should come from the drafttek list
        pick_names = {pick.player for pick in picks}
        drafttek_names = {p.name for p in drafttek_infos}
        self.assertTrue(pick_names.issubset(drafttek_names))

    def test_simulate_draft_carries_metadata_from_drafttek_prospects(self) -> None:
        drafttek_infos = [
            ProspectInfo(name=f"Player {i}", position="QB", college="State U", bio_url=f"https://example.com/{i}")
            for i in range(1, 300)
        ]
        with patch("nfl_draft.get_drafttek_2026_prospects", return_value=drafttek_infos):
            picks = simulate_draft()
        for pick in picks:
            self.assertNotEqual("", pick.position)
            self.assertNotEqual("", pick.college)
            self.assertTrue(pick.bio_url.startswith("https://"))

    def test_simulate_draft_falls_back_to_remote_csv_when_drafttek_empty(self) -> None:
        with (
            patch("nfl_draft.get_drafttek_2026_prospects", return_value=[]),
            patch("nfl_draft.get_real_2026_prospects", return_value=[f"Remote Player {i}" for i in range(1, 300)]),
        ):
            picks = simulate_draft()
        self.assertEqual(224, len(picks))
        self.assertTrue(all(pick.player.startswith("Remote Player") for pick in picks))

    def test_simulate_draft_accepts_string_prospects_for_backward_compatibility(self) -> None:
        string_prospects = [f"Test Player {i:03d}" for i in range(1, 225)]
        picks = simulate_draft(prospects=string_prospects)
        self.assertEqual(224, len(picks))
        pick_names = {pick.player for pick in picks}
        self.assertTrue(pick_names.issubset(set(string_prospects)))

    def test_simulate_draft_accepts_mixed_prospect_infos(self) -> None:
        mixed = [
            ProspectInfo(name="Info Player", position="QB", college="State U"),
            "String Player",
        ] * 112
        picks = simulate_draft(prospects=mixed)
        self.assertEqual(224, len(picks))

    def test_get_drafttek_2026_prospects_returns_cached_result(self) -> None:
        get_drafttek_2026_prospects.cache_clear()
        with patch("nfl_draft._load_drafttek_prospects") as mock_load:
            mock_load.return_value = [ProspectInfo(name="Cached Player")]
            result1 = get_drafttek_2026_prospects()
            result2 = get_drafttek_2026_prospects()
        self.assertEqual(1, mock_load.call_count)
        self.assertEqual(result1, result2)
        get_drafttek_2026_prospects.cache_clear()


class DraftOrderDataTests(unittest.TestCase):
    """Tests for the hardcoded 2026 draft order constants."""

    def test_round_1_has_32_picks(self) -> None:
        self.assertEqual(32, len(_DRAFT_ORDER_2026_ROUND_1))

    def test_round_1_first_24_picks_match_announced_order(self) -> None:
        expected_first_24 = [
            "Las Vegas Raiders",
            "New York Jets",
            "Arizona Cardinals",
            "Tennessee Titans",
            "New York Giants",
            "Cleveland Browns",
            "Washington Commanders",
            "New Orleans Saints",
            "Kansas City Chiefs",
            "Cincinnati Bengals",
            "Miami Dolphins",
            "Dallas Cowboys",
            "Los Angeles Rams",
            "Baltimore Ravens",
            "Tampa Bay Buccaneers",
            "New York Jets",
            "Detroit Lions",
            "Minnesota Vikings",
            "Carolina Panthers",
            "Dallas Cowboys",
            "Pittsburgh Steelers",
            "Los Angeles Chargers",
            "Philadelphia Eagles",
            "Cleveland Browns",
        ]
        self.assertEqual(expected_first_24, _DRAFT_ORDER_2026_ROUND_1[:24])

    def test_rounds_2_to_7_has_32_teams(self) -> None:
        self.assertEqual(32, len(_DRAFT_ORDER_2026_ROUNDS_2_TO_7))

    def test_rounds_2_to_7_all_unique(self) -> None:
        self.assertEqual(32, len(set(_DRAFT_ORDER_2026_ROUNDS_2_TO_7)))

    def test_hardcoded_order_has_correct_total_picks(self) -> None:
        order = _hardcoded_draft_order_2026()
        # 32 picks in round 1 + 32 picks × 6 rounds = 224 total
        self.assertEqual(32 + 32 * 6, len(order))

    def test_hardcoded_order_round_numbers(self) -> None:
        order = _hardcoded_draft_order_2026()
        rounds = {round_num for round_num, _ in order}
        self.assertEqual(set(range(1, 8)), rounds)

    def test_hardcoded_order_round_1_teams_match_constant(self) -> None:
        order = _hardcoded_draft_order_2026()
        r1_teams = [team for round_num, team in order if round_num == 1]
        self.assertEqual(_DRAFT_ORDER_2026_ROUND_1, r1_teams)


class FetchDraftOrderTests(unittest.TestCase):
    """Tests for _fetch_draft_order_from_nflverse and get_draft_order."""

    def _make_csv_bytes(self, rows: list[dict]) -> bytes:
        buf = io.StringIO()
        if rows:
            writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        return buf.getvalue().encode("utf-8")

    @patch("nfl_draft.urlopen")
    def test_returns_empty_list_on_network_error(self, mock_urlopen: Mock) -> None:
        from urllib.error import URLError
        mock_urlopen.side_effect = URLError("timeout")
        result = _fetch_draft_order_from_nflverse(2026)
        self.assertEqual([], result)

    @patch("nfl_draft.urlopen")
    def test_returns_empty_list_when_year_not_in_csv(self, mock_urlopen: Mock) -> None:
        csv_bytes = self._make_csv_bytes([
            {"season": "2025", "round": "1", "pick": "1", "team": "TEN", "pfr_player_name": "Cam Ward"},
        ])
        mock_response = Mock()
        mock_response.read.return_value = csv_bytes
        mock_urlopen.return_value.__enter__.return_value = mock_response
        result = _fetch_draft_order_from_nflverse(2026)
        self.assertEqual([], result)

    @patch("nfl_draft.urlopen")
    def test_parses_round_and_team_correctly(self, mock_urlopen: Mock) -> None:
        csv_bytes = self._make_csv_bytes([
            {"season": "2026", "round": "1", "pick": "1", "team": "LVR", "pfr_player_name": ""},
            {"season": "2026", "round": "1", "pick": "2", "team": "NYJ", "pfr_player_name": ""},
            {"season": "2026", "round": "2", "pick": "33", "team": "LVR", "pfr_player_name": ""},
        ])
        mock_response = Mock()
        mock_response.read.return_value = csv_bytes
        mock_urlopen.return_value.__enter__.return_value = mock_response
        result = _fetch_draft_order_from_nflverse(2026)
        self.assertEqual(3, len(result))
        self.assertEqual((1, "Las Vegas Raiders"), result[0])
        self.assertEqual((1, "New York Jets"), result[1])
        self.assertEqual((2, "Las Vegas Raiders"), result[2])

    @patch("nfl_draft.urlopen")
    def test_unknown_abbreviation_kept_as_is(self, mock_urlopen: Mock) -> None:
        csv_bytes = self._make_csv_bytes([
            {"season": "2026", "round": "1", "pick": "1", "team": "XYZ", "pfr_player_name": ""},
        ])
        mock_response = Mock()
        mock_response.read.return_value = csv_bytes
        mock_urlopen.return_value.__enter__.return_value = mock_response
        result = _fetch_draft_order_from_nflverse(2026)
        self.assertEqual(1, len(result))
        self.assertEqual("XYZ", result[0][1])

    def test_get_draft_order_falls_back_to_hardcoded_for_2026(self) -> None:
        get_draft_order.cache_clear()
        with patch("nfl_draft._fetch_draft_order_from_nflverse", return_value=[]):
            result = get_draft_order(2026)
        self.assertEqual(_hardcoded_draft_order_2026(), result)
        get_draft_order.cache_clear()

    @patch("nfl_draft._fetch_draft_order_from_nflverse")
    def test_get_draft_order_returns_remote_when_available(self, mock_fetch: Mock) -> None:
        get_draft_order.cache_clear()
        remote = [(1, "Las Vegas Raiders"), (1, "New York Jets")]
        mock_fetch.return_value = remote
        result = get_draft_order(2026)
        self.assertEqual(remote, result)
        get_draft_order.cache_clear()

    def test_get_draft_order_returns_empty_for_unknown_year_when_fetch_fails(self) -> None:
        get_draft_order.cache_clear()
        with patch("nfl_draft._fetch_draft_order_from_nflverse", return_value=[]):
            result = get_draft_order(1999)
        self.assertEqual([], result)
        get_draft_order.cache_clear()


class SimulateDraftWithPickSequenceTests(unittest.TestCase):
    """Tests for simulate_draft's pick_sequence parameter."""

    def _small_sequence(self) -> list[tuple[int, str]]:
        """A minimal two-round, two-team pick sequence for fast tests."""
        return [
            (1, "Las Vegas Raiders"),
            (1, "New York Jets"),
            (2, "Las Vegas Raiders"),
            (2, "New York Jets"),
        ]

    def test_pick_sequence_overrides_teams_and_rounds(self) -> None:
        seq = self._small_sequence()
        picks = simulate_draft(
            pick_sequence=seq,
            prospects=["Player A", "Player B", "Player C", "Player D"],
        )
        self.assertEqual(4, len(picks))
        self.assertEqual("Las Vegas Raiders", picks[0].team)
        self.assertEqual("New York Jets", picks[1].team)
        self.assertEqual(1, picks[0].round_number)
        self.assertEqual(2, picks[2].round_number)

    def test_overall_pick_numbers_are_sequential(self) -> None:
        seq = self._small_sequence()
        picks = simulate_draft(
            pick_sequence=seq,
            prospects=["A", "B", "C", "D"],
        )
        self.assertEqual([1, 2, 3, 4], [p.overall_pick for p in picks])

    def test_round_pick_resets_each_round(self) -> None:
        seq = self._small_sequence()
        picks = simulate_draft(
            pick_sequence=seq,
            prospects=["A", "B", "C", "D"],
        )
        self.assertEqual(1, picks[0].round_pick)
        self.assertEqual(2, picks[1].round_pick)
        self.assertEqual(1, picks[2].round_pick)  # resets for round 2
        self.assertEqual(2, picks[3].round_pick)

    def test_team_with_two_picks_appears_twice(self) -> None:
        seq = [
            (1, "Las Vegas Raiders"),
            (1, "New York Jets"),
            (1, "Las Vegas Raiders"),  # trade pick
        ]
        picks = simulate_draft(
            pick_sequence=seq,
            prospects=["A", "B", "C"],
        )
        raiders_picks = [p for p in picks if p.team == "Las Vegas Raiders"]
        self.assertEqual(2, len(raiders_picks))

    def test_pick_sequence_none_preserves_legacy_behaviour(self) -> None:
        picks = simulate_draft(
            teams=["Team Alpha", "Team Beta"],
            rounds=2,
            prospects=["A", "B", "C", "D"],
        )
        self.assertEqual(4, len(picks))
        self.assertEqual("Team Alpha", picks[0].team)
        self.assertEqual("Team Beta", picks[1].team)

    def test_hardcoded_order_produces_correct_round_1_teams(self) -> None:
        order = _hardcoded_draft_order_2026()
        prospect_list = [f"Player {i}" for i in range(1, len(order) + 1)]
        picks = simulate_draft(pick_sequence=order, prospects=prospect_list)
        r1_picks = [p for p in picks if p.round_number == 1]
        self.assertEqual(32, len(r1_picks))
        self.assertEqual("Las Vegas Raiders", r1_picks[0].team)
        self.assertEqual("New York Jets", r1_picks[1].team)
        self.assertEqual("Cleveland Browns", r1_picks[5].team)


if __name__ == "__main__":
    unittest.main()
