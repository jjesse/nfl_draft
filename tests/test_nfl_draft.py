import unittest
from collections import Counter

from nfl_draft import get_team_picks, simulate_draft


class DraftSimulationTests(unittest.TestCase):
    def test_simulate_draft_creates_224_picks(self) -> None:
        picks = simulate_draft()
        self.assertEqual(224, len(picks))
        self.assertEqual(list(range(1, 225)), [pick.overall_pick for pick in picks])

    def test_each_team_gets_seven_picks(self) -> None:
        picks = simulate_draft()
        by_team = Counter(pick.team for pick in picks)
        self.assertEqual(32, len(by_team))
        self.assertTrue(all(count == 7 for count in by_team.values()))

    def test_can_query_team_picks(self) -> None:
        picks = simulate_draft()
        dallas_picks = get_team_picks(picks, "Dallas Cowboys")
        self.assertEqual(7, len(dallas_picks))
        self.assertTrue(all(pick.team == "Dallas Cowboys" for pick in dallas_picks))


if __name__ == "__main__":
    unittest.main()
