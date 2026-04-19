# nfl_draft

2026 NFL Draft simulator with:

- a Python CLI for draft simulation and team lookup
- a static web UI for GitHub Pages (round-by-round and team-by-team views)

By default, the CLI tries to load **real 2026 draft picks** from the
[`nfl_data_py`](https://pypi.org/project/nfl-data-py/) package (sourced from
the [nflverse](https://github.com/nflverse) project). This data becomes
available after the draft concludes. Until then, the CLI falls back to a
simulated draft using real 2026 player names from the public
Mock-Draft-Database dataset (or generated placeholders if that source is also
unavailable).

## Setup

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Use Python 3.11 for dependency compatibility (`nfl-data-py` currently resolves to
`pandas<2`, which is not installable on Python 3.12 in this workflow).

## Python CLI usage

### Run a full 7-round draft (real picks when available, simulation otherwise)

```bash
python nfl_draft.py
```

The header line (`# Source: …`) tells you whether you are viewing real picks
from `nfl_data_py` or a simulated draft.

### View picks for a single team (example: Dallas Cowboys)

```bash
python nfl_draft.py --team "Dallas Cowboys"
```

## GitHub Actions – draft data refresh

The `Update Draft Data` workflow (`.github/workflows/update_draft.yml`) refreshes
`docs/draft_data.json` on each push to `main`/`master` (including merges) and can also be run
manually from **Actions → Update Draft Data → Run workflow**:

1. It installs the Python dependencies from `requirements.txt`.
2. It runs `generate_data.py`, which tries `nfl_data_py` first and falls back
   to a simulation when real picks are not yet available.
3. If the generated file changed, it commits and pushes the update to the
   repository. GitHub Pages then serves the fresh data immediately.

To run the data generation locally:

```bash
python generate_data.py
```

This writes `docs/draft_data.json`, which the web UI fetches on load.

## Web UI (GitHub Pages)

The web app is in `/docs`:

- `/docs/index.html`
- `/docs/app.js`
- `/docs/styles.css`

Features:

- **Round by round** view: choose a round and see all 32 picks
- **Team by team** view: choose a team and see all 7 picks

To publish on GitHub Pages for this repository:

1. Go to **Settings → Pages**
2. Set source to **Deploy from a branch**
3. Select your branch and the **/docs** folder
4. Save and open the generated site URL

To include it from `jjesse.github.io`, link to the published `nfl_draft` page.

## Draft pick order

The simulator always uses the correct team ordering for every pick, including
traded picks.  The pick order is resolved through the following fallback chain:

1. **nflverse data release** – `get_draft_order(year)` fetches the completed
   draft order from the [nflverse-data draft_picks release]
   (https://github.com/nflverse/nflverse-data/releases/tag/draft_picks).
   This CSV is updated after each draft concludes and uses the same team
   abbreviations as the rest of the codebase.
2. **Hardcoded 2026 order** – When nflverse data is not yet available (i.e.,
   the draft has not concluded), a built-in 2026 order is used:
   - **Round 1 picks 1–24** are the officially announced order (including all
     traded picks such as "Los Angeles Rams from Atlanta Falcons via trade").
   - **Round 1 picks 25–32** are estimated from 2025 season standings.
   - **Rounds 2–7** use an approximate inverse-standings order for all 32 teams
     (including teams that traded away their Round 1 pick).

The `source` field in `docs/draft_data.json` (and the `# Source:` header in
CLI output) tells you which data was used.

## Drafttek prospect data

The simulator uses the Drafttek 2026 top-600 big board as the primary player
pool for simulated drafts. The data is stored locally so no internet access is
required at runtime:

- `drafttek_2026_top600_with_bio.csv` – ranked prospect list with position,
  college, height, weight, class, and bio URL.
- `drafttek_2026_top600_with_bio.json` – the same data in JSON format.

The simulation fallback order is:

1. **Real picks** from `nfl_data_py` (used after the draft concludes).
2. **Drafttek top-600 CSV** (primary simulation source, sorted by rank).
3. **Mock-Draft-Database remote CSV** (secondary simulation source).
4. **Generated placeholders** (`Prospect 001`, `Prospect 002`, …).

### Refreshing the Drafttek data

`scrape_draftek_bio.py` is a standalone utility script that re-scrapes the
[DraftTek big board](https://www.drafttek.com/2026-NFL-Draft-Big-Board/) and
overwrites the two data files above. Run it manually when you want to pull
fresh rankings:

```bash
pip install requests beautifulsoup4 pandas tqdm
python scrape_draftek_bio.py
```

After running the scraper, commit the updated CSV/JSON files and run
`python generate_data.py` to regenerate `docs/draft_data.json`.

## Run tests

```bash
python -m unittest discover -s tests -v
```
