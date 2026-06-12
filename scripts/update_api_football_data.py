from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


BASE_URL = "https://v3.football.api-sports.io"
WORLD_CUP_LEAGUE_ID = 1
DEFAULT_SEASON = 2026
DEFAULT_OUTPUT_DIR = Path("data/external/api_football")
DEFAULT_REPORT = Path("data/reports/api_football_ingestion_report.zh-CN.md")
FINAL_STATUSES = {"FT", "AET", "PEN"}
CSV_SCHEMAS = {
    "fixtures_2026.csv": [
        "season", "fixture_id", "date_utc", "timestamp", "status_long", "status_short", "elapsed", "round",
        "venue_id", "venue_name", "venue_city", "home_team_id", "home_team", "home_winner", "away_team_id",
        "away_team", "away_winner", "home_goals", "away_goals", "halftime_home_goals", "halftime_away_goals",
        "fulltime_home_goals", "fulltime_away_goals", "extratime_home_goals", "extratime_away_goals",
        "penalty_home_goals", "penalty_away_goals",
    ],
    "teams_2026.csv": [
        "season", "team_id", "team", "team_code", "country", "founded", "national", "logo", "home_venue_id",
        "home_venue_name", "home_venue_city", "home_venue_capacity", "home_venue_surface",
    ],
    "standings_2026.csv": [
        "season", "league_id", "league", "group", "rank", "team_id", "team", "points", "goals_diff", "form",
        "description", "played", "wins", "draws", "losses", "goals_for", "goals_against", "updated",
    ],
    "injuries_2026.csv": [
        "season", "fixture_id", "fixture_date", "player_id", "player", "player_photo", "team_id", "team",
        "type", "reason",
    ],
    "odds_2026.csv": [
        "season", "fixture_id", "fixture_timezone", "fixture_date", "league_id", "league", "bookmaker_id",
        "bookmaker", "bet_id", "bet", "outcome", "odd",
    ],
    "fixture_statistics_2026.csv": ["fixture_id", "team_id", "team"],
    "lineups_2026.csv": [
        "fixture_id", "team_id", "team", "formation", "coach_id", "coach", "lineup_section", "player_id",
        "player", "number", "position", "grid",
    ],
    "fixture_players_2026.csv": [
        "fixture_id", "team_id", "team", "player_id", "player", "number", "position", "rating", "minutes",
        "captain", "substitute", "offsides", "shots_total", "shots_on", "goals", "goals_conceded", "assists",
        "saves", "passes_total", "passes_key", "passes_accuracy", "tackles_total", "blocks", "interceptions",
        "duels_total", "duels_won", "dribbles_attempts", "dribbles_success", "fouls_drawn", "fouls_committed",
        "yellow_cards", "red_cards", "penalty_won", "penalty_committed", "penalty_scored", "penalty_missed",
        "penalty_saved",
    ],
    "events_2026.csv": [
        "fixture_id", "elapsed", "extra", "team_id", "team", "player_id", "player", "assist_id", "assist",
        "type", "detail", "comments",
    ],
}


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def load_streamlit_secrets(path: Path = Path(".streamlit/secrets.toml")) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line or line.startswith("["):
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in {"API_FOOTBALL_KEY", "APISPORTS_KEY", "api_football_key"}:
            os.environ.setdefault(key.upper(), value.strip().strip("\"'"))


def api_key_from_env() -> str:
    load_dotenv()
    load_streamlit_secrets()
    api_key = (
        os.environ.get("API_FOOTBALL_KEY")
        or os.environ.get("APISPORTS_KEY")
        or os.environ.get("API_FOOTBALL_API_KEY")
    )
    if not api_key:
        raise SystemExit(
            "Missing API key. Set API_FOOTBALL_KEY in your environment, .env, or .streamlit/secrets.toml."
        )
    return api_key


def safe_name(path: str, params: dict[str, Any] | None) -> str:
    bits = [path.strip("/").replace("/", "_")]
    if params:
        bits.extend(f"{key}_{value}" for key, value in sorted(params.items()))
    return "__".join(bits) + ".json"


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def request_json(
    path: str,
    params: dict[str, Any] | None,
    api_key: str,
    timeout: int,
    retries: int,
    sleep_seconds: float,
) -> dict[str, Any]:
    query = f"?{urllib.parse.urlencode(params)}" if params else ""
    url = f"{BASE_URL}{path}{query}"
    request = urllib.request.Request(url, headers={"x-apisports-key": api_key})
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
            time.sleep(sleep_seconds)
            return data
        except urllib.error.HTTPError as error:
            last_error = error
            if error.code in {429, 500, 502, 503, 504} and attempt < retries:
                time.sleep(sleep_seconds * (attempt + 2))
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error
            if attempt < retries:
                time.sleep(sleep_seconds * (attempt + 2))
                continue
            raise
    raise RuntimeError(f"API request failed: {last_error}")


def fetch_and_store(
    output_dir: Path,
    path: str,
    params: dict[str, Any] | None,
    api_key: str,
    timeout: int,
    retries: int,
    sleep_seconds: float,
) -> dict[str, Any]:
    data = request_json(path, params, api_key, timeout, retries, sleep_seconds)
    write_json(output_dir / "raw" / safe_name(path, params), data)
    return data


def response_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    response = data.get("response", [])
    return response if isinstance(response, list) else []


def flatten_fixtures(data: dict[str, Any], season: int) -> pd.DataFrame:
    rows = []
    for item in response_rows(data):
        fixture = item.get("fixture", {})
        league = item.get("league", {})
        teams = item.get("teams", {})
        goals = item.get("goals", {})
        score = item.get("score", {})
        rows.append(
            {
                "season": season,
                "fixture_id": fixture.get("id"),
                "date_utc": fixture.get("date"),
                "timestamp": fixture.get("timestamp"),
                "status_long": fixture.get("status", {}).get("long"),
                "status_short": fixture.get("status", {}).get("short"),
                "elapsed": fixture.get("status", {}).get("elapsed"),
                "round": league.get("round"),
                "venue_id": fixture.get("venue", {}).get("id"),
                "venue_name": fixture.get("venue", {}).get("name"),
                "venue_city": fixture.get("venue", {}).get("city"),
                "home_team_id": teams.get("home", {}).get("id"),
                "home_team": teams.get("home", {}).get("name"),
                "home_winner": teams.get("home", {}).get("winner"),
                "away_team_id": teams.get("away", {}).get("id"),
                "away_team": teams.get("away", {}).get("name"),
                "away_winner": teams.get("away", {}).get("winner"),
                "home_goals": goals.get("home"),
                "away_goals": goals.get("away"),
                "halftime_home_goals": score.get("halftime", {}).get("home"),
                "halftime_away_goals": score.get("halftime", {}).get("away"),
                "fulltime_home_goals": score.get("fulltime", {}).get("home"),
                "fulltime_away_goals": score.get("fulltime", {}).get("away"),
                "extratime_home_goals": score.get("extratime", {}).get("home"),
                "extratime_away_goals": score.get("extratime", {}).get("away"),
                "penalty_home_goals": score.get("penalty", {}).get("home"),
                "penalty_away_goals": score.get("penalty", {}).get("away"),
            }
        )
    return pd.DataFrame(rows)


def flatten_teams(data: dict[str, Any], season: int) -> pd.DataFrame:
    rows = []
    for item in response_rows(data):
        team = item.get("team", {})
        venue = item.get("venue", {})
        rows.append(
            {
                "season": season,
                "team_id": team.get("id"),
                "team": team.get("name"),
                "team_code": team.get("code"),
                "country": team.get("country"),
                "founded": team.get("founded"),
                "national": team.get("national"),
                "logo": team.get("logo"),
                "home_venue_id": venue.get("id"),
                "home_venue_name": venue.get("name"),
                "home_venue_city": venue.get("city"),
                "home_venue_capacity": venue.get("capacity"),
                "home_venue_surface": venue.get("surface"),
            }
        )
    return pd.DataFrame(rows).drop_duplicates()


def flatten_standings(data: dict[str, Any], season: int) -> pd.DataFrame:
    rows = []
    for league_item in response_rows(data):
        league = league_item.get("league", {})
        for group_rows in league.get("standings", []) or []:
            for item in group_rows:
                all_stats = item.get("all", {})
                rows.append(
                    {
                        "season": season,
                        "league_id": league.get("id"),
                        "league": league.get("name"),
                        "group": item.get("group"),
                        "rank": item.get("rank"),
                        "team_id": item.get("team", {}).get("id"),
                        "team": item.get("team", {}).get("name"),
                        "points": item.get("points"),
                        "goals_diff": item.get("goalsDiff"),
                        "form": item.get("form"),
                        "description": item.get("description"),
                        "played": all_stats.get("played"),
                        "wins": all_stats.get("win"),
                        "draws": all_stats.get("draw"),
                        "losses": all_stats.get("lose"),
                        "goals_for": all_stats.get("goals", {}).get("for"),
                        "goals_against": all_stats.get("goals", {}).get("against"),
                        "updated": item.get("update"),
                    }
                )
    return pd.DataFrame(rows)


def flatten_injuries(data: dict[str, Any], season: int) -> pd.DataFrame:
    rows = []
    for item in response_rows(data):
        fixture = item.get("fixture", {})
        player = item.get("player", {})
        team = item.get("team", {})
        rows.append(
            {
                "season": season,
                "fixture_id": fixture.get("id"),
                "fixture_date": fixture.get("date"),
                "player_id": player.get("id"),
                "player": player.get("name"),
                "player_photo": player.get("photo"),
                "team_id": team.get("id"),
                "team": team.get("name"),
                "type": item.get("type"),
                "reason": item.get("reason"),
            }
        )
    return pd.DataFrame(rows)


def flatten_odds(data: dict[str, Any], season: int) -> pd.DataFrame:
    rows = []
    for item in response_rows(data):
        fixture = item.get("fixture", {})
        league = item.get("league", {})
        for bookmaker in item.get("bookmakers", []) or []:
            for bet in bookmaker.get("bets", []) or []:
                for value in bet.get("values", []) or []:
                    rows.append(
                        {
                            "season": season,
                            "fixture_id": fixture.get("id"),
                            "fixture_timezone": fixture.get("timezone"),
                            "fixture_date": fixture.get("date"),
                            "league_id": league.get("id"),
                            "league": league.get("name"),
                            "bookmaker_id": bookmaker.get("id"),
                            "bookmaker": bookmaker.get("name"),
                            "bet_id": bet.get("id"),
                            "bet": bet.get("name"),
                            "outcome": value.get("value"),
                            "odd": value.get("odd"),
                        }
                    )
    return pd.DataFrame(rows)


def flatten_fixture_statistics(raw_by_fixture: dict[int, dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for fixture_id, data in raw_by_fixture.items():
        for team_block in response_rows(data):
            team = team_block.get("team", {})
            row = {"fixture_id": fixture_id, "team_id": team.get("id"), "team": team.get("name")}
            for stat in team_block.get("statistics", []) or []:
                name = str(stat.get("type", "")).lower().replace(" ", "_").replace("-", "_")
                row[name] = stat.get("value")
            rows.append(row)
    return pd.DataFrame(rows)


def flatten_lineups(raw_by_fixture: dict[int, dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for fixture_id, data in raw_by_fixture.items():
        for item in response_rows(data):
            team = item.get("team", {})
            coach = item.get("coach", {})
            for section, players in [("startxi", item.get("startXI", [])), ("substitute", item.get("substitutes", []))]:
                for player_item in players or []:
                    player = player_item.get("player", {})
                    rows.append(
                        {
                            "fixture_id": fixture_id,
                            "team_id": team.get("id"),
                            "team": team.get("name"),
                            "formation": item.get("formation"),
                            "coach_id": coach.get("id"),
                            "coach": coach.get("name"),
                            "lineup_section": section,
                            "player_id": player.get("id"),
                            "player": player.get("name"),
                            "number": player.get("number"),
                            "position": player.get("pos"),
                            "grid": player.get("grid"),
                        }
                    )
    return pd.DataFrame(rows)


def flatten_events(raw_by_fixture: dict[int, dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for fixture_id, data in raw_by_fixture.items():
        for item in response_rows(data):
            rows.append(
                {
                    "fixture_id": fixture_id,
                    "elapsed": item.get("time", {}).get("elapsed"),
                    "extra": item.get("time", {}).get("extra"),
                    "team_id": item.get("team", {}).get("id"),
                    "team": item.get("team", {}).get("name"),
                    "player_id": item.get("player", {}).get("id"),
                    "player": item.get("player", {}).get("name"),
                    "assist_id": item.get("assist", {}).get("id"),
                    "assist": item.get("assist", {}).get("name"),
                    "type": item.get("type"),
                    "detail": item.get("detail"),
                    "comments": item.get("comments"),
                }
            )
    return pd.DataFrame(rows)


def flatten_fixture_players(raw_by_fixture: dict[int, dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for fixture_id, data in raw_by_fixture.items():
        for team_block in response_rows(data):
            team = team_block.get("team", {})
            for player_block in team_block.get("players", []) or []:
                player = player_block.get("player", {})
                stats = (player_block.get("statistics") or [{}])[0]
                rows.append(
                    {
                        "fixture_id": fixture_id,
                        "team_id": team.get("id"),
                        "team": team.get("name"),
                        "player_id": player.get("id"),
                        "player": player.get("name"),
                        "number": player.get("number"),
                        "position": player.get("pos"),
                        "rating": stats.get("games", {}).get("rating"),
                        "minutes": stats.get("games", {}).get("minutes"),
                        "captain": stats.get("games", {}).get("captain"),
                        "substitute": stats.get("games", {}).get("substitute"),
                        "offsides": stats.get("offsides"),
                        "shots_total": stats.get("shots", {}).get("total"),
                        "shots_on": stats.get("shots", {}).get("on"),
                        "goals": stats.get("goals", {}).get("total"),
                        "goals_conceded": stats.get("goals", {}).get("conceded"),
                        "assists": stats.get("goals", {}).get("assists"),
                        "saves": stats.get("goals", {}).get("saves"),
                        "passes_total": stats.get("passes", {}).get("total"),
                        "passes_key": stats.get("passes", {}).get("key"),
                        "passes_accuracy": stats.get("passes", {}).get("accuracy"),
                        "tackles_total": stats.get("tackles", {}).get("total"),
                        "blocks": stats.get("tackles", {}).get("blocks"),
                        "interceptions": stats.get("tackles", {}).get("interceptions"),
                        "duels_total": stats.get("duels", {}).get("total"),
                        "duels_won": stats.get("duels", {}).get("won"),
                        "dribbles_attempts": stats.get("dribbles", {}).get("attempts"),
                        "dribbles_success": stats.get("dribbles", {}).get("success"),
                        "fouls_drawn": stats.get("fouls", {}).get("drawn"),
                        "fouls_committed": stats.get("fouls", {}).get("committed"),
                        "yellow_cards": stats.get("cards", {}).get("yellow"),
                        "red_cards": stats.get("cards", {}).get("red"),
                        "penalty_won": stats.get("penalty", {}).get("won"),
                        "penalty_committed": stats.get("penalty", {}).get("commited"),
                        "penalty_scored": stats.get("penalty", {}).get("scored"),
                        "penalty_missed": stats.get("penalty", {}).get("missed"),
                        "penalty_saved": stats.get("penalty", {}).get("saved"),
                    }
                )
    return pd.DataFrame(rows)


def write_csv(path: Path, frame: pd.DataFrame, columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if frame.empty and columns:
        frame = pd.DataFrame(columns=columns)
    frame.to_csv(path, index=False)


def write_report(
    path: Path,
    output_dir: Path,
    season: int,
    frames: dict[str, pd.DataFrame],
    fixture_ids: list[int],
    errors: list[dict[str, Any]],
) -> None:
    lines = [
        "# API-Football Pro 数据管道报告",
        "",
        f"- Generated：{datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "- Provider：API-Football / API-Sports",
        f"- League：World Cup，league={WORLD_CUP_LEAGUE_ID}",
        f"- Season：{season}",
        "- API key：未写入代码；运行时从 `.env`、环境变量或 Streamlit secrets 读取",
        "",
        "## 输出目录",
        "",
        f"- Raw JSON：`{output_dir / 'raw'}`",
        f"- Clean CSV：`{output_dir / 'processed'}`",
        "",
        "## 输出行数",
        "",
    ]
    for name, frame in frames.items():
        lines.append(f"- `{name}`：{len(frame)} rows")
    lines.extend(
        [
            "",
            "## Fixture-level 抓取范围",
            "",
            f"- Fixture IDs：{len(fixture_ids)}",
            "",
            "## 错误或 API 限制",
            "",
        ]
    )
    if errors:
        for error in errors:
            lines.append(f"- `{error['path']}` {error['params']}：{error['error']}")
    else:
        lines.append("- None")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def collect_error(path: str, params: dict[str, Any], data: dict[str, Any]) -> dict[str, Any] | None:
    errors = data.get("errors")
    if not errors:
        return None
    return {"path": path, "params": params, "error": errors}


def fetch_endpoint(
    output_dir: Path,
    path: str,
    params: dict[str, Any],
    api_key: str,
    timeout: int,
    retries: int,
    sleep_seconds: float,
    errors: list[dict[str, Any]],
) -> dict[str, Any]:
    print(f"Fetching {path} {params}")
    data = fetch_and_store(output_dir, path, params, api_key, timeout, retries, sleep_seconds)
    error = collect_error(path, params, data)
    if error:
        errors.append(error)
    return data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update API-Football Pro World Cup 2026 data pipeline.")
    parser.add_argument("--season", type=int, default=DEFAULT_SEASON)
    parser.add_argument("--league", type=int, default=WORLD_CUP_LEAGUE_ID)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--sleep", type=float, default=0.35)
    parser.add_argument("--fixture-limit", type=int, default=None, help="Optional limit for fixture-level endpoints.")
    parser.add_argument("--skip-fixture-details", action="store_true", help="Only fetch season-level endpoints.")
    parser.add_argument("--completed-only", action="store_true", help="Only fetch fixture-level data for completed fixtures.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    api_key = api_key_from_env()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    processed_dir = args.output_dir / "processed"
    errors: list[dict[str, Any]] = []

    base_params = {"league": args.league, "season": args.season}
    fixtures_raw = fetch_endpoint(args.output_dir, "/fixtures", base_params, api_key, args.timeout, args.retries, args.sleep, errors)
    teams_raw = fetch_endpoint(args.output_dir, "/teams", base_params, api_key, args.timeout, args.retries, args.sleep, errors)
    standings_raw = fetch_endpoint(args.output_dir, "/standings", base_params, api_key, args.timeout, args.retries, args.sleep, errors)
    injuries_raw = fetch_endpoint(args.output_dir, "/injuries", base_params, api_key, args.timeout, args.retries, args.sleep, errors)
    odds_raw = fetch_endpoint(args.output_dir, "/odds", base_params, api_key, args.timeout, args.retries, args.sleep, errors)

    fixtures = flatten_fixtures(fixtures_raw, args.season)
    teams = flatten_teams(teams_raw, args.season)
    standings = flatten_standings(standings_raw, args.season)
    injuries = flatten_injuries(injuries_raw, args.season)
    odds = flatten_odds(odds_raw, args.season)

    fixture_ids: list[int] = []
    if not fixtures.empty and "fixture_id" in fixtures:
        detail_fixtures = fixtures.copy()
        if args.completed_only:
            detail_fixtures = detail_fixtures[detail_fixtures["status_short"].isin(FINAL_STATUSES)]
        fixture_ids = [int(value) for value in detail_fixtures["fixture_id"].dropna().tolist()]
        if args.fixture_limit is not None:
            fixture_ids = fixture_ids[: args.fixture_limit]

    statistics_raw: dict[int, dict[str, Any]] = {}
    lineups_raw: dict[int, dict[str, Any]] = {}
    players_raw: dict[int, dict[str, Any]] = {}
    events_raw: dict[int, dict[str, Any]] = {}

    if not args.skip_fixture_details:
        for fixture_id in fixture_ids:
            params = {"fixture": fixture_id}
            statistics_raw[fixture_id] = fetch_endpoint(args.output_dir, "/fixtures/statistics", params, api_key, args.timeout, args.retries, args.sleep, errors)
            lineups_raw[fixture_id] = fetch_endpoint(args.output_dir, "/fixtures/lineups", params, api_key, args.timeout, args.retries, args.sleep, errors)
            players_raw[fixture_id] = fetch_endpoint(args.output_dir, "/fixtures/players", params, api_key, args.timeout, args.retries, args.sleep, errors)
            events_raw[fixture_id] = fetch_endpoint(args.output_dir, "/fixtures/events", params, api_key, args.timeout, args.retries, args.sleep, errors)

    fixture_statistics = flatten_fixture_statistics(statistics_raw)
    lineups = flatten_lineups(lineups_raw)
    fixture_players = flatten_fixture_players(players_raw)
    events = flatten_events(events_raw)

    frames = {
        f"fixtures_{args.season}.csv": fixtures,
        f"teams_{args.season}.csv": teams,
        f"standings_{args.season}.csv": standings,
        f"injuries_{args.season}.csv": injuries,
        f"odds_{args.season}.csv": odds,
        f"fixture_statistics_{args.season}.csv": fixture_statistics,
        f"lineups_{args.season}.csv": lineups,
        f"fixture_players_{args.season}.csv": fixture_players,
        f"events_{args.season}.csv": events,
    }
    for filename, frame in frames.items():
        schema_key = filename.replace(str(args.season), str(DEFAULT_SEASON))
        write_csv(processed_dir / filename, frame, CSV_SCHEMAS.get(schema_key))

    write_report(args.report, args.output_dir, args.season, frames, fixture_ids, errors)
    print(f"Wrote processed CSV files to {processed_dir}")
    print(f"Wrote report to {args.report}")


if __name__ == "__main__":
    main()
