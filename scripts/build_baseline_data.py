from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd


DEFAULT_SCHEDULE = Path("/Users/jay/Desktop/FIFA/DATA/赛程表.csv")
DEFAULT_ELO = Path("/Users/jay/Desktop/FIFA/DATA/elo ratings 1872-2025.csv")
DEFAULT_MATCHES = Path(
    "/Users/jay/Desktop/FIFA/DATA/International results from 1872 to 2026 daily update 20260608/all_matches.csv"
)
DEFAULT_OUTPUT = Path("data/processed/world_cup_2026_baseline.csv")
DEFAULT_REPORT = Path("data/reports/world_cup_2026_baseline_quality.md")

NAME_MAP = {
    "USA": "United States",
    "Czech Republic": "Czechia",
    "DR Congo": "Democratic Republic of Congo",
    "Bosnia & Herzegovina": "Bosnia and Herzegovina",
}

PLACEHOLDER_RE = re.compile(r"^(?:[123][A-L](?:/[A-L])*(?:/[A-L])?|W\d+|L\d+)$")
CANADA_CITIES = {"Toronto", "Vancouver"}
MEXICO_CITIES = {"Mexico City", "Guadalajara (Zapopan)"}


def normalize_team(value: object) -> str | None:
    if pd.isna(value):
        return None
    team = str(value).replace("\xa0", " ").strip()
    return NAME_MAP.get(team, team)


def is_placeholder(value: object) -> bool:
    team = normalize_team(value)
    return bool(team and PLACEHOLDER_RE.match(team))


def build_match_id(game: pd.Series, source_row: int) -> str:
    if pd.notna(game["num"]):
        return f"wc2026_m{int(game['num']):03d}"
    return f"wc2026_r{source_row:03d}"


def venue_country(city: object) -> str | None:
    if pd.isna(city):
        return None
    city_text = str(city).strip()
    if city_text in CANADA_CITIES:
        return "Canada"
    if city_text in MEXICO_CITIES:
        return "Mexico"
    return "United States"


def venue_flags(home_team: str | None, away_team: str | None, city: object) -> dict[str, object]:
    country = venue_country(city)
    home_advantage = int(home_team == country) if home_team else pd.NA
    away_advantage = int(away_team == country) if away_team else pd.NA
    neutral_venue = int(home_advantage == 0 and away_advantage == 0) if pd.notna(home_advantage) and pd.notna(away_advantage) else pd.NA
    return {
        "venue_country": country,
        "home_advantage": home_advantage,
        "away_advantage": away_advantage,
        "neutral_venue": neutral_venue,
    }


def parse_dates(series: pd.Series) -> pd.Series:
    try:
        return pd.to_datetime(series, errors="coerce", format="mixed")
    except ValueError:
        return series.map(lambda value: pd.to_datetime(value, errors="coerce"))


def parse_match_datetime_utc(date_value: object, time_value: object) -> pd.Timestamp | pd.NaT:
    if pd.isna(date_value) or pd.isna(time_value):
        return pd.NaT
    time_text = str(time_value).strip()
    match = re.match(r"^(\d{1,2}:\d{2})\s+UTC([+-]\d{1,2})$", time_text)
    if not match:
        return pd.NaT
    clock, offset_hours = match.groups()
    local_dt = pd.to_datetime(f"{date_value} {clock}", errors="coerce")
    if pd.isna(local_dt):
        return pd.NaT
    return local_dt - pd.to_timedelta(int(offset_hours), unit="h")


def load_inputs(schedule_path: Path, elo_path: Path, matches_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    schedule = pd.read_csv(schedule_path)
    elo = pd.read_csv(elo_path)
    matches = pd.read_csv(matches_path)

    schedule["date"] = parse_dates(schedule["date"])
    schedule["home_team_std"] = schedule["home_team"].map(normalize_team)
    schedule["away_team_std"] = schedule["away_team"].map(normalize_team)
    schedule["home_is_placeholder"] = schedule["home_team"].map(is_placeholder)
    schedule["away_is_placeholder"] = schedule["away_team"].map(is_placeholder)
    schedule["match_datetime_utc"] = [
        parse_match_datetime_utc(row.date, row.time) for row in schedule.itertuples(index=False)
    ]

    elo["date"] = parse_dates(elo["date"])
    elo["team_std"] = elo["team"].map(normalize_team)

    matches["date"] = parse_dates(matches["date"])
    matches["home_team_std"] = matches["home_team"].map(normalize_team)
    matches["away_team_std"] = matches["away_team"].map(normalize_team)
    matches["home_result"] = (matches["home_score"] > matches["away_score"]).astype(int)
    matches["away_result"] = (matches["away_score"] > matches["home_score"]).astype(int)
    matches["is_draw"] = (matches["home_score"] == matches["away_score"]).astype(int)
    return schedule, elo, matches


def latest_elo_before_match(elo: pd.DataFrame, team: str | None, match_date: pd.Timestamp) -> dict[str, object]:
    if not team or pd.isna(match_date):
        return {"rating": pd.NA, "rating_date": pd.NaT, "rating_change": pd.NA}
    team_rows = elo[(elo["team_std"] == team) & (elo["date"] < match_date)].sort_values("date")
    if team_rows.empty:
        return {"rating": pd.NA, "rating_date": pd.NaT, "rating_change": pd.NA}
    row = team_rows.iloc[-1]
    return {"rating": row["rating"], "rating_date": row["date"], "rating_change": row["change"]}


def team_form(matches: pd.DataFrame, team: str | None, match_date: pd.Timestamp, n: int = 10) -> dict[str, object]:
    keys = {
        "matches": pd.NA,
        "wins": pd.NA,
        "draws": pd.NA,
        "losses": pd.NA,
        "win_rate": pd.NA,
        "points_per_match": pd.NA,
        "goals_for_avg": pd.NA,
        "goals_against_avg": pd.NA,
    }
    if not team or pd.isna(match_date):
        return keys

    played = matches[
        (matches["date"] < match_date)
        & ((matches["home_team_std"] == team) | (matches["away_team_std"] == team))
    ].sort_values("date")
    if played.empty:
        return keys
    recent = played.tail(n).copy()
    is_home = recent["home_team_std"] == team
    goals_for = recent["home_score"].where(is_home, recent["away_score"])
    goals_against = recent["away_score"].where(is_home, recent["home_score"])
    wins = (goals_for > goals_against).sum()
    draws = (goals_for == goals_against).sum()
    losses = (goals_for < goals_against).sum()
    total = len(recent)
    points = wins * 3 + draws
    return {
        "matches": total,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "win_rate": wins / total,
        "points_per_match": points / total,
        "goals_for_avg": goals_for.mean(),
        "goals_against_avg": goals_against.mean(),
    }


def h2h_features(matches: pd.DataFrame, home_team: str | None, away_team: str | None, match_date: pd.Timestamp) -> dict[str, object]:
    empty = {
        "h2h_matches": pd.NA,
        "h2h_home_team_wins": pd.NA,
        "h2h_away_team_wins": pd.NA,
        "h2h_draws": pd.NA,
        "h2h_home_team_win_rate": pd.NA,
        "h2h_away_team_win_rate": pd.NA,
        "h2h_draw_rate": pd.NA,
        "h2h_home_goals_avg": pd.NA,
        "h2h_away_goals_avg": pd.NA,
        "h2h_last_match_date": pd.NaT,
    }
    if not home_team or not away_team or pd.isna(match_date):
        return empty

    rows = matches[
        (matches["date"] < match_date)
        & (
            ((matches["home_team_std"] == home_team) & (matches["away_team_std"] == away_team))
            | ((matches["home_team_std"] == away_team) & (matches["away_team_std"] == home_team))
        )
    ].sort_values("date")
    if rows.empty:
        return empty

    home_wins = 0
    away_wins = 0
    draws = 0
    home_goals = []
    away_goals = []
    for row in rows.itertuples(index=False):
        if row.home_team_std == home_team:
            hg, ag = row.home_score, row.away_score
        else:
            hg, ag = row.away_score, row.home_score
        home_goals.append(hg)
        away_goals.append(ag)
        if hg > ag:
            home_wins += 1
        elif hg < ag:
            away_wins += 1
        else:
            draws += 1

    total = len(rows)
    return {
        "h2h_matches": total,
        "h2h_home_team_wins": home_wins,
        "h2h_away_team_wins": away_wins,
        "h2h_draws": draws,
        "h2h_home_team_win_rate": home_wins / total,
        "h2h_away_team_win_rate": away_wins / total,
        "h2h_draw_rate": draws / total,
        "h2h_home_goals_avg": sum(home_goals) / total,
        "h2h_away_goals_avg": sum(away_goals) / total,
        "h2h_last_match_date": rows["date"].max(),
    }


def build_baseline(schedule: pd.DataFrame, elo: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for idx, game in schedule.reset_index(drop=True).iterrows():
        match_date = game["date"]
        home_team = game["home_team_std"]
        away_team = game["away_team_std"]
        home_elo = latest_elo_before_match(elo, home_team, match_date)
        away_elo = latest_elo_before_match(elo, away_team, match_date)
        home_form = team_form(matches, home_team, match_date, n=10)
        away_form = team_form(matches, away_team, match_date, n=10)
        h2h = h2h_features(matches, home_team, away_team, match_date)
        flags = venue_flags(home_team, away_team, game["city"])

        record = {
            "match_id": build_match_id(game, idx + 1),
            "source_row": idx + 1,
            "competition": game["competition"],
            "round": game["round"],
            "group": game["group"],
            "date": match_date.date().isoformat() if pd.notna(match_date) else pd.NA,
            "time": game["time"],
            "match_datetime_utc": game["match_datetime_utc"],
            "city": game["city"],
            "venue_country": flags["venue_country"],
            "home_team": home_team,
            "away_team": away_team,
            "home_is_placeholder": game["home_is_placeholder"],
            "away_is_placeholder": game["away_is_placeholder"],
            "home_advantage": flags["home_advantage"] if not game["home_is_placeholder"] else pd.NA,
            "away_advantage": flags["away_advantage"] if not game["away_is_placeholder"] else pd.NA,
            "neutral_venue": flags["neutral_venue"] if not game["home_is_placeholder"] and not game["away_is_placeholder"] else pd.NA,
            "home_elo": home_elo["rating"],
            "away_elo": away_elo["rating"],
            "elo_diff_home_minus_away": (
                home_elo["rating"] - away_elo["rating"]
                if pd.notna(home_elo["rating"]) and pd.notna(away_elo["rating"])
                else pd.NA
            ),
            "home_elo_date": home_elo["rating_date"],
            "away_elo_date": away_elo["rating_date"],
            "home_elo_last_change": home_elo["rating_change"],
            "away_elo_last_change": away_elo["rating_change"],
        }
        record.update({f"home_recent10_{key}": value for key, value in home_form.items()})
        record.update({f"away_recent10_{key}": value for key, value in away_form.items()})
        record.update(h2h)
        rows.append(record)

    baseline = pd.DataFrame(rows)
    return baseline


def write_report(
    report_path: Path,
    baseline: pd.DataFrame,
    schedule: pd.DataFrame,
    elo: pd.DataFrame,
    matches: pd.DataFrame,
) -> None:
    known = baseline[~baseline["home_is_placeholder"] & ~baseline["away_is_placeholder"]]
    missing_elo = baseline[
        (~baseline["home_is_placeholder"] & baseline["home_elo"].isna())
        | (~baseline["away_is_placeholder"] & baseline["away_elo"].isna())
    ]
    placeholder_games = baseline[baseline["home_is_placeholder"] | baseline["away_is_placeholder"]]
    schedule_teams = sorted(set(schedule["home_team_std"]).union(schedule["away_team_std"]))
    elo_teams = set(elo["team_std"])
    match_teams = set(matches["home_team_std"]).union(matches["away_team_std"])
    unresolved_elo = [team for team in schedule_teams if team and not is_placeholder(team) and team not in elo_teams]
    unresolved_matches = [team for team in schedule_teams if team and not is_placeholder(team) and team not in match_teams]

    lines = [
        "# World Cup 2026 Baseline Data Quality",
        "",
        f"- Schedule rows: {len(schedule)}",
        f"- Baseline rows: {len(baseline)}",
        f"- Known-team games: {len(known)}",
        f"- Placeholder games: {len(placeholder_games)}",
        f"- ELO source rows: {len(elo)}",
        f"- Historical match source rows: {len(matches)}",
        f"- Known games with missing ELO: {len(missing_elo)}",
        "",
        "## Name Standardization",
        "",
        "- `USA` -> `United States`",
        "- `Czech Republic` -> `Czechia`",
        "- `DR Congo` -> `Democratic Republic of Congo` for ELO lookup",
        "- `Bosnia & Herzegovina` -> `Bosnia and Herzegovina`",
        "- Non-breaking spaces in source ELO names are normalized to regular spaces",
        "",
        "## Unresolved Known Teams",
        "",
        f"- Missing from ELO after mapping: {', '.join(unresolved_elo) if unresolved_elo else 'None'}",
        f"- Missing from historical matches after mapping: {', '.join(unresolved_matches) if unresolved_matches else 'None'}",
        "",
        "## Notes",
        "",
        "- Knockout-stage placeholders such as `1A`, `2B`, and `W73` are kept as rows with blank model features.",
        "- ELO is taken as the latest available rating before the scheduled match date.",
        "- Recent form uses each team's latest 10 historical matches before the scheduled match date.",
        "- H2H features are calculated from all prior meetings before the scheduled match date.",
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build World Cup 2026 baseline match data.")
    parser.add_argument("--schedule", type=Path, default=DEFAULT_SCHEDULE)
    parser.add_argument("--elo", type=Path, default=DEFAULT_ELO)
    parser.add_argument("--matches", type=Path, default=DEFAULT_MATCHES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    schedule, elo, matches = load_inputs(args.schedule, args.elo, args.matches)
    baseline = build_baseline(schedule, elo, matches)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    baseline.to_csv(args.output, index=False)
    write_report(args.report, baseline, schedule, elo, matches)
    print(f"Wrote {len(baseline)} rows to {args.output}")
    print(f"Wrote quality report to {args.report}")


if __name__ == "__main__":
    main()
