# nfl_draft

Simple 2026 NFL Draft simulator and team pick lookup.

By default, the simulator pulls real 2026 player names from the public
Mock-Draft-Database dataset and falls back to generated placeholders only if
the remote source is unavailable.

## Run a full 7-round simulation (224 picks)

```bash
python nfl_draft.py
```

## View picks for a single team (example: Dallas Cowboys)

```bash
python nfl_draft.py --team "Dallas Cowboys"
```

## Run tests

```bash
python -m unittest discover -s tests -v
```
