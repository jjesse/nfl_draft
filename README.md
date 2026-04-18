# nfl_draft

2026 NFL Draft simulator with:

- a Python CLI for draft simulation and team lookup
- a static web UI for GitHub Pages (round-by-round and team-by-team views)

By default, the CLI simulator pulls real 2026 player names from the public
Mock-Draft-Database dataset and falls back to generated placeholders only if
the remote source is unavailable.

## Python CLI usage

### Run a full 7-round simulation (224 picks)

```bash
python nfl_draft.py
```

### View picks for a single team (example: Dallas Cowboys)

```bash
python nfl_draft.py --team "Dallas Cowboys"
```

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
