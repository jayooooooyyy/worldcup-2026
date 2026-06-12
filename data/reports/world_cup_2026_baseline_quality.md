# World Cup 2026 Baseline Data Quality

- Schedule rows: 104
- Baseline rows: 104
- Known-team games: 72
- Placeholder games: 32
- ELO source rows: 6678
- Historical match source rows: 51607
- Known games with missing ELO: 0

## Name Standardization

- `USA` -> `United States`
- `Czech Republic` -> `Czechia`
- `DR Congo` -> `Democratic Republic of Congo` for ELO lookup
- `Bosnia & Herzegovina` -> `Bosnia and Herzegovina`
- Non-breaking spaces in source ELO names are normalized to regular spaces

## Unresolved Known Teams

- Missing from ELO after mapping: None
- Missing from historical matches after mapping: None

## Notes

- Knockout-stage placeholders such as `1A`, `2B`, and `W73` are kept as rows with blank model features.
- ELO is taken as the latest available rating before the scheduled match date.
- Recent form uses each team's latest 10 historical matches before the scheduled match date.
- H2H features are calculated from all prior meetings before the scheduled match date.
