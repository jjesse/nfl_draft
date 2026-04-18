import unittest
from collections import Counter
from unittest.mock import Mock, patch

from nfl_draft import _fetch_real_2026_prospects, get_team_picks, simulate_draft


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


if __name__ == "__main__":
    unittest.main()
