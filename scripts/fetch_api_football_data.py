from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import pandas as pd


BASE_URL = "https://v3.football.api-sports.io"
WORLD_CUP_LEAGUE_ID = 1
DEFAULT_SEASONS = [2022]
DEFAULT_OUTPUT_DIR = Path("data/external/api_football")
DEFAULT_REPORT = Path("data/reports/api_football_fetch_report.zh-CN.md")


def api_get(path: str, params: dict[str, Any] | None, api_key: str) -> dict[str, Any]:
    query = f"?{urllib.parse.urlencode(params)}" if params else ""
    request = urllib.request.Request(
        f"{BASE_URL}{path}{query}",
        headers={"x-apisports-key": api_key},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_name(path: str, params: dict[str, Any] | None) -> str:
    bits = [path.strip("/").replace("/", "_")]
    if params:
        bits.extend(f"{key}_{value}" for key, value in sorted(params.items()))
    return "__".join(bits) + ".json"


def fetch_and_store(output_dir: Path, path: str, params: dict[str, Any] | None, api_key: str) -> dict[str, Any]:
    data = api_get(path, params, api_key)
    write_json(output_dir / "raw" / safe_name(path, params), data)
    time.sleep(0.25)
    return data


def flatten_fixtures(raw_by_season: dict[int, dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for season, data in raw_by_season.items():
        for item in data.get("response", []):
            rows.append(
                {
                    "season": season,
                    "fixture_id": item["fixture"]["id"],
                    "date_utc": item["fixture"]["date"],
                    "timestamp": item["fixture"]["timestamp"],
                    "round": item["league"]["round"],
                    "venue_name": item["fixture"]["venue"]["name"],
                    "venue_city": item["fixture"]["venue"]["city"],
                    "home_team_id": item["teams"]["home"]["id"],
                    "home_team": item["teams"]["home"]["name"],
                    "away_team_id": item["teams"]["away"]["id"],
                    "away_team": item["teams"]["away"]["name"],
                    "home_goals": item["goals"]["home"],
                    "away_goals": item["goals"]["away"],
                    "home_winner": item["teams"]["home"]["winner"],
                    "away_winner": item["teams"]["away"]["winner"],
                    "status": item["fixture"]["status"]["short"],
                }
            )
    return pd.DataFrame(rows)


def flatten_teams(raw_by_season: dict[int, dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for season, data in raw_by_season.items():
        for item in data.get("response", []):
            rows.append(
                {
                    "season": season,
                    "team_id": item["team"]["id"],
                    "team": item["team"]["name"],
                    "team_code": item["team"]["code"],
                    "country": item["team"]["country"],
                    "founded": item["team"]["founded"],
                    "national": item["team"]["national"],
                    "home_venue_name": item["venue"]["name"],
                    "home_venue_city": item["venue"]["city"],
                    "home_venue_capacity": item["venue"]["capacity"],
                    "home_venue_surface": item["venue"]["surface"],
                }
            )
    return pd.DataFrame(rows).drop_duplicates()


def flatten_standings(raw_by_season: dict[int, dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for season, data in raw_by_season.items():
        for league in data.get("response", []):
            for group_rows in league.get("league", {}).get("standings", []):
                for item in group_rows:
                    rows.append(
                        {
                            "season": season,
                            "group": item["group"],
                            "rank": item["rank"],
                            "team_id": item["team"]["id"],
                            "team": item["team"]["name"],
                            "points": item["points"],
                            "goals_diff": item["goalsDiff"],
                            "form": item["form"],
                            "description": item["description"],
                            "played": item["all"]["played"],
                            "wins": item["all"]["win"],
                            "draws": item["all"]["draw"],
                            "losses": item["all"]["lose"],
                            "goals_for": item["all"]["goals"]["for"],
                            "goals_against": item["all"]["goals"]["against"],
                        }
                    )
    return pd.DataFrame(rows)


def flatten_top_players(raw_by_metric: dict[str, dict[int, dict[str, Any]]]) -> pd.DataFrame:
    rows = []
    for metric, raw_by_season in raw_by_metric.items():
        for season, data in raw_by_season.items():
            for rank, item in enumerate(data.get("response", []), start=1):
                stats = item.get("statistics", [{}])[0]
                player = item["player"]
                rows.append(
                    {
                        "season": season,
                        "metric": metric,
                        "rank": rank,
                        "player_id": player["id"],
                        "player": player["name"],
                        "age": player["age"],
                        "nationality": player["nationality"],
                        "injured": player["injured"],
                        "team_id": stats.get("team", {}).get("id"),
                        "team": stats.get("team", {}).get("name"),
                        "appearances": stats.get("games", {}).get("appearences"),
                        "lineups": stats.get("games", {}).get("lineups"),
                        "minutes": stats.get("games", {}).get("minutes"),
                        "position": stats.get("games", {}).get("position"),
                        "rating": stats.get("games", {}).get("rating"),
                        "goals": stats.get("goals", {}).get("total"),
                        "assists": stats.get("goals", {}).get("assists"),
                        "shots_total": stats.get("shots", {}).get("total"),
                        "shots_on": stats.get("shots", {}).get("on"),
                        "passes_total": stats.get("passes", {}).get("total"),
                        "passes_key": stats.get("passes", {}).get("key"),
                        "yellow_cards": stats.get("cards", {}).get("yellow"),
                        "red_cards": stats.get("cards", {}).get("red"),
                    }
                )
    return pd.DataFrame(rows)


def write_report(
    report_path: Path,
    output_dir: Path,
    seasons: list[int],
    fixtures: pd.DataFrame,
    teams: pd.DataFrame,
    standings: pd.DataFrame,
    top_players: pd.DataFrame,
    errors: list[dict[str, Any]],
) -> None:
    lines = [
        "# API-Football 数据抓取报告",
        "",
        "## 数据源",
        "",
        "- Provider：API-Football / API-Sports",
        "- Host：v3.football.api-sports.io",
        "- League：World Cup，league id = 1",
        "- API key：未写入项目文件；运行脚本时通过环境变量 `API_FOOTBALL_KEY` 读取",
        "",
        "## 已抓取数据",
        "",
        f"- Seasons requested：{', '.join(map(str, seasons))}",
        f"- Fixtures rows：{len(fixtures)}",
        f"- Teams rows：{len(teams)}",
        f"- Standings rows：{len(standings)}",
        f"- Top players rows：{len(top_players)}",
        "",
        "## 输出文件",
        "",
        f"- `{output_dir / 'api_football_world_cup_fixtures.csv'}`",
        f"- `{output_dir / 'api_football_world_cup_teams.csv'}`",
        f"- `{output_dir / 'api_football_world_cup_standings.csv'}`",
        f"- `{output_dir / 'api_football_world_cup_top_players.csv'}`",
        f"- `{output_dir / 'raw'}`：原始 JSON 响应",
        "",
        "## 重要限制",
        "",
        "- 当前 Free plan 无法访问 World Cup 2026 season，接口提示可访问范围为 2022 到 2024。",
        "- World Cup 的 injuries coverage 为 false，因此伤病接口目前没有可用世界杯伤病数据。",
        "- 当前脚本先抓历史世界杯数据，用于模型增强、回测和未来数据结构对接。",
        "",
        "## API 错误或限制",
        "",
    ]
    if errors:
        for error in errors:
            lines.append(f"- `{error['path']}` {error['params']}：{error['errors']}")
    else:
        lines.append("- None")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_seasons(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch API-Football World Cup data.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--seasons", default=",".join(map(str, DEFAULT_SEASONS)))
    args = parser.parse_args()

    api_key = os.environ.get("API_FOOTBALL_KEY")
    if not api_key:
        raise SystemExit("Missing API_FOOTBALL_KEY environment variable.")

    seasons = parse_seasons(args.seasons)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    errors: list[dict[str, Any]] = []
    fetch_and_store(args.output_dir, "/leagues", {"id": WORLD_CUP_LEAGUE_ID}, api_key)

    fixtures_raw: dict[int, dict[str, Any]] = {}
    teams_raw: dict[int, dict[str, Any]] = {}
    standings_raw: dict[int, dict[str, Any]] = {}
    top_players_raw: dict[str, dict[int, dict[str, Any]]] = {
        "topscorers": {},
        "topassists": {},
        "topyellowcards": {},
        "topredcards": {},
    }

    for season in seasons:
        for target, path, params in [
            (fixtures_raw, "/fixtures", {"league": WORLD_CUP_LEAGUE_ID, "season": season}),
            (teams_raw, "/teams", {"league": WORLD_CUP_LEAGUE_ID, "season": season}),
            (standings_raw, "/standings", {"league": WORLD_CUP_LEAGUE_ID, "season": season}),
        ]:
            data = fetch_and_store(args.output_dir, path, params, api_key)
            if data.get("errors"):
                errors.append({"path": path, "params": params, "errors": data.get("errors")})
            else:
                target[season] = data

        for metric in top_players_raw:
            path = f"/players/{metric}"
            params = {"league": WORLD_CUP_LEAGUE_ID, "season": season}
            data = fetch_and_store(args.output_dir, path, params, api_key)
            if data.get("errors"):
                errors.append({"path": path, "params": params, "errors": data.get("errors")})
            else:
                top_players_raw[metric][season] = data

    fixtures = flatten_fixtures(fixtures_raw)
    teams = flatten_teams(teams_raw)
    standings = flatten_standings(standings_raw)
    top_players = flatten_top_players(top_players_raw)

    fixtures.to_csv(args.output_dir / "api_football_world_cup_fixtures.csv", index=False)
    teams.to_csv(args.output_dir / "api_football_world_cup_teams.csv", index=False)
    standings.to_csv(args.output_dir / "api_football_world_cup_standings.csv", index=False)
    top_players.to_csv(args.output_dir / "api_football_world_cup_top_players.csv", index=False)
    write_report(args.report, args.output_dir, seasons, fixtures, teams, standings, top_players, errors)
    print(f"Wrote API-Football data to {args.output_dir}")
    print(f"Wrote report to {args.report}")


if __name__ == "__main__":
    main()
