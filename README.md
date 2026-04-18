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

## GitHub Actions – automatic data refresh

A scheduled workflow (`.github/workflows/update_draft.yml`) runs every day at
noon UTC and refreshes `docs/draft_data.json` automatically:

1. It installs the Python dependencies from `requirements.txt`.
2. It runs `generate_data.py`, which tries `nfl_data_py` first and falls back
   to a simulation when real picks are not yet available.
3. If the generated file changed, it commits and pushes the update to the
   repository. GitHub Pages then serves the fresh data immediately.

You can also trigger the workflow manually from
**Actions → Update Draft Data → Run workflow**.

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

## Run tests

```bash
python -m unittest discover -s tests -v
```
