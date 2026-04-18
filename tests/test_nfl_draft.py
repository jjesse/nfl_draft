import unittest
from collections import Counter
from unittest.mock import MagicMock, Mock, patch

from nfl_draft import (
    NFL_TEAM_ABBREVIATIONS,
    _fetch_actual_draft_picks,
    _fetch_real_2026_prospects,
    _load_prospects_from_csv_text,
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


if __name__ == "__main__":
    unittest.main()
