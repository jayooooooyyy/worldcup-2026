# FIFA World Cup Prediction Baseline

This project starts with a match-level baseline table for World Cup 2026 prediction work.

## Files

- `scripts/build_baseline_data.py` builds the baseline dataset from the schedule, ELO ratings, and historical international match results.
- `data/processed/world_cup_2026_baseline.csv` is the generated baseline table.
- `data/reports/world_cup_2026_baseline_quality.md` summarizes row counts, name mappings, and missing-data checks.

## Baseline Grain

Each row is one scheduled World Cup 2026 match.

The table keeps the raw schedule teams and adds standardized team names. Knockout-stage placeholders such as `1A`, `2B`, and `W73` are preserved with `home_is_placeholder` / `away_is_placeholder` flags, because those rows need group-stage simulation before they can receive team-level features.

## Current Feature Blocks

- Schedule context: round, group, date, UTC datetime, city, match number.
- Team identity: raw and standardized home/away team names.
- ELO: latest available rating before match date for both teams, plus home-away rating difference.
- Recent form: latest 10 historical matches for each team before match date.
- Head to head: all prior meetings between the two teams before match date.

## Rebuild

```bash
python3 scripts/build_baseline_data.py
```

## Suggested Next Steps

1. Train a simple baseline probability model using ELO difference, recent form, and H2H features.
2. Add market-oriented output columns: home win probability, draw probability, away win probability, fair odds, and market edge.
3. Build group-stage simulation so knockout placeholders can be filled dynamically.
4. Add a Polymarket mapping layer with market slug, condition ID, outcome labels, and live price snapshots.
