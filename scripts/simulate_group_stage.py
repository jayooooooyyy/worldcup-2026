from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_BASELINE = Path("data/processed/world_cup_2026_predictions_final.csv")
DEFAULT_TRAINING = Path("data/processed/international_match_training.csv")
DEFAULT_OUTPUT = Path("data/processed/group_simulation_2026.csv")
DEFAULT_REPORT = Path("data/reports/group_simulation_v1.zh-CN.md")
OUTCOMES = ["home_win", "draw", "away_win"]


def scoreline_pools(training: pd.DataFrame) -> dict[str, list[tuple[int, int]]]:
    recent = training[pd.to_datetime(training["date"], errors="coerce").dt.year >= 1990].copy()
    pools: dict[str, list[tuple[int, int]]] = {}
    for outcome in OUTCOMES:
        rows = recent[recent["result"] == outcome]
        pools[outcome] = list(zip(rows["home_score"].astype(int), rows["away_score"].astype(int)))
    return pools


def choose_scoreline(rng: np.random.Generator, outcome: str, pools: dict[str, list[tuple[int, int]]]) -> tuple[int, int]:
    pool = pools[outcome]
    if not pool:
        fallback = {"home_win": (1, 0), "draw": (1, 1), "away_win": (0, 1)}
        return fallback[outcome]
    return pool[int(rng.integers(0, len(pool)))]


def blank_record(team: str, group: str) -> dict[str, object]:
    return {
        "team": team,
        "group": group,
        "played": 0,
        "points": 0,
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "goals_for": 0,
        "goals_against": 0,
        "goal_diff": 0,
    }


def rank_group(records: dict[str, dict[str, object]], rng: np.random.Generator) -> list[dict[str, object]]:
    ranked = list(records.values())
    for row in ranked:
        row["tie_noise"] = rng.random()
    ranked.sort(
        key=lambda row: (
            row["points"],
            row["goal_diff"],
            row["goals_for"],
            row["tie_noise"],
        ),
        reverse=True,
    )
    for index, row in enumerate(ranked, start=1):
        row["rank"] = index
    return ranked


def update_table(table: dict[str, dict[str, object]], home: str, away: str, home_score: int, away_score: int) -> None:
    table[home]["played"] += 1
    table[away]["played"] += 1
    table[home]["goals_for"] += home_score
    table[home]["goals_against"] += away_score
    table[away]["goals_for"] += away_score
    table[away]["goals_against"] += home_score
    table[home]["goal_diff"] = table[home]["goals_for"] - table[home]["goals_against"]
    table[away]["goal_diff"] = table[away]["goals_for"] - table[away]["goals_against"]

    if home_score > away_score:
        table[home]["points"] += 3
        table[home]["wins"] += 1
        table[away]["losses"] += 1
    elif home_score < away_score:
        table[away]["points"] += 3
        table[away]["wins"] += 1
        table[home]["losses"] += 1
    else:
        table[home]["points"] += 1
        table[away]["points"] += 1
        table[home]["draws"] += 1
        table[away]["draws"] += 1


def simulate_once(group_matches: pd.DataFrame, pools: dict[str, list[tuple[int, int]]], rng: np.random.Generator) -> list[dict[str, object]]:
    group_tables: dict[str, dict[str, dict[str, object]]] = {}
    for group, rows in group_matches.groupby("group"):
        teams = sorted(set(rows["home_team"]).union(rows["away_team"]))
        group_tables[group] = {team: blank_record(team, group) for team in teams}

    for row in group_matches.itertuples(index=False):
        probabilities = np.array([row.home_win_prob, row.draw_prob, row.away_win_prob], dtype=float)
        probabilities = probabilities / probabilities.sum()
        outcome = rng.choice(OUTCOMES, p=probabilities)
        home_score, away_score = choose_scoreline(rng, outcome, pools)
        update_table(group_tables[row.group], row.home_team, row.away_team, home_score, away_score)

    ranked_rows = []
    third_place = []
    for group, table in group_tables.items():
        ranked = rank_group(table, rng)
        ranked_rows.extend(ranked)
        third_place.append(ranked[2])

    for row in ranked_rows:
        row["advance_round_of_32"] = row["rank"] <= 2

    for row in third_place:
        row["third_tie_noise"] = rng.random()
    third_place.sort(
        key=lambda row: (
            row["points"],
            row["goal_diff"],
            row["goals_for"],
            row["third_tie_noise"],
        ),
        reverse=True,
    )
    for row in third_place[:8]:
        row["advance_round_of_32"] = True

    return ranked_rows


def simulate(group_matches: pd.DataFrame, training: pd.DataFrame, iterations: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    pools = scoreline_pools(training)
    counters = defaultdict(lambda: defaultdict(float))
    totals = defaultdict(lambda: defaultdict(float))

    for _ in range(iterations):
        rows = simulate_once(group_matches, pools, rng)
        for row in rows:
            team = row["team"]
            group = row["group"]
            counters[team]["group"] = group
            counters[team][f"rank_{row['rank']}_count"] += 1
            counters[team]["top2_count"] += int(row["rank"] <= 2)
            counters[team]["third_count"] += int(row["rank"] == 3)
            counters[team]["advance_round_of_32_count"] += int(row["advance_round_of_32"])
            totals[team]["points"] += row["points"]
            totals[team]["goal_diff"] += row["goal_diff"]
            totals[team]["goals_for"] += row["goals_for"]

    output_rows = []
    for team, values in counters.items():
        row = {"team": team, "group": values["group"]}
        advance = values["advance_round_of_32_count"] / iterations
        row["avg_points"] = totals[team]["points"] / iterations
        row["prob_group_1st"] = values["rank_1_count"] / iterations
        row["prob_group_2nd"] = values["rank_2_count"] / iterations
        row["prob_group_3rd"] = values["rank_3_count"] / iterations
        row["prob_group_4th"] = values["rank_4_count"] / iterations
        row["prob_advance"] = advance
        row["prob_eliminated"] = 1 - advance
        output_rows.append(row)

    columns = [
        "team",
        "group",
        "avg_points",
        "prob_group_1st",
        "prob_group_2nd",
        "prob_group_3rd",
        "prob_group_4th",
        "prob_advance",
        "prob_eliminated",
    ]
    result = pd.DataFrame(output_rows)[columns].sort_values(["group", "prob_advance"], ascending=[True, False])
    return result


def markdown_table(frame: pd.DataFrame) -> str:
    headers = list(frame.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in frame.itertuples(index=False):
        values = []
        for value in row:
            if isinstance(value, float):
                values.append(f"{value:.4f}")
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def write_report(path: Path, result: pd.DataFrame, iterations: int) -> None:
    lines = [
        "# 2026 世界杯小组赛 Monte Carlo 模拟报告",
        "",
        f"- 模拟次数：{iterations}",
        "- 输入：`world_cup_2026_predictions_final.csv` 中的 calibrated_v3 单场胜平负概率",
        "- 比分生成：从 1990 年以来历史国家队比赛中，按胜/平/负结果抽取相同方向的历史比分",
        "- 小组排名规则近似：积分、净胜球、进球数、随机微小扰动",
        "- 晋级规则：每组前二直接晋级，12 个小组第三中排名最好的 8 队晋级",
        "",
        "## 各组出线概率",
        "",
    ]
    for group, rows in result.groupby("group"):
        lines.append(f"### {group}")
        cols = ["team", "avg_points", "prob_group_1st", "prob_group_2nd", "prob_group_3rd", "prob_advance", "prob_eliminated"]
        lines.append(markdown_table(rows[cols]))
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate World Cup 2026 group stage.")
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE, help="Final prediction CSV with calibrated_v3 probabilities.")
    parser.add_argument("--training", type=Path, default=DEFAULT_TRAINING)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--iterations", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    baseline = pd.read_csv(args.baseline)
    training = pd.read_csv(args.training)
    group_matches = baseline[
        baseline["group"].notna()
        & baseline["home_win_prob"].notna()
        & baseline["draw_prob"].notna()
        & baseline["away_win_prob"].notna()
    ].copy()
    result = simulate(group_matches, training, args.iterations, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False)
    write_report(args.report, result, args.iterations)
    print(f"Wrote group simulation to {args.output}")
    print(f"Wrote report to {args.report}")


if __name__ == "__main__":
    main()
