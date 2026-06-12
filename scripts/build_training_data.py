from __future__ import annotations

import argparse
from collections import defaultdict, deque
from pathlib import Path

import pandas as pd

from build_baseline_data import DEFAULT_ELO, DEFAULT_MATCHES, normalize_team, parse_dates


DEFAULT_OUTPUT = Path("data/processed/international_match_training.csv")
DEFAULT_REPORT = Path("data/reports/international_match_training_quality.zh-CN.md")


def load_sources(elo_path: Path, matches_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    elo = pd.read_csv(elo_path)
    matches = pd.read_csv(matches_path)

    elo["date"] = parse_dates(elo["date"])
    elo["team"] = elo["team"].map(normalize_team)
    elo = elo.dropna(subset=["date", "team"]).sort_values(["team", "date"])

    matches["date"] = parse_dates(matches["date"])
    matches["home_team"] = matches["home_team"].map(normalize_team)
    matches["away_team"] = matches["away_team"].map(normalize_team)
    matches["country"] = matches["country"].map(normalize_team)
    matches = matches.dropna(subset=["date", "home_team", "away_team"]).copy()
    matches = matches.reset_index(drop=True)
    matches["source_match_no"] = matches.index + 1
    matches["home_advantage"] = ((matches["neutral"] == False) & (matches["country"] == matches["home_team"])).astype(int)
    matches["away_advantage"] = ((matches["neutral"] == False) & (matches["country"] == matches["away_team"])).astype(int)
    matches["neutral_venue"] = matches["neutral"].astype(int)
    return elo, matches


def side_elo_features(matches: pd.DataFrame, elo: pd.DataFrame, side: str) -> pd.DataFrame:
    team_col = f"{side}_team"
    left = matches[["source_match_no", "date", team_col]].rename(columns={team_col: "team"})
    feature_parts = []

    for team, left_group in left.groupby("team", sort=False):
        team_elo = elo[elo["team"] == team][["date", "rating", "change"]].rename(columns={"date": "elo_date"})
        if team_elo.empty:
            part = left_group[["source_match_no"]].copy()
            part[f"{side}_elo"] = pd.Series([pd.NA] * len(part), dtype="Float64")
            part[f"{side}_elo_date"] = pd.Series([pd.NaT] * len(part), dtype="datetime64[ns]")
            part[f"{side}_elo_last_change"] = pd.Series([pd.NA] * len(part), dtype="Float64")
        else:
            merged = pd.merge_asof(
                left_group.sort_values("date"),
                team_elo.sort_values("elo_date"),
                left_on="date",
                right_on="elo_date",
                direction="backward",
                allow_exact_matches=False,
            )
            part = merged[["source_match_no", "rating", "elo_date", "change"]].rename(
                columns={
                    "rating": f"{side}_elo",
                    "elo_date": f"{side}_elo_date",
                    "change": f"{side}_elo_last_change",
                }
            )
        feature_parts.append(part)

    return pd.concat(feature_parts, ignore_index=True)


def add_elo_features(matches: pd.DataFrame, elo: pd.DataFrame) -> pd.DataFrame:
    home = side_elo_features(matches, elo, "home")
    away = side_elo_features(matches, elo, "away")
    out = matches.merge(home, on="source_match_no", how="left").merge(away, on="source_match_no", how="left")
    out["elo_diff_home_minus_away"] = out["home_elo"] - out["away_elo"]
    return out


def build_team_perspective(matches: pd.DataFrame) -> pd.DataFrame:
    home = pd.DataFrame(
        {
            "source_match_no": matches["source_match_no"],
            "date": matches["date"],
            "side": "home",
            "team": matches["home_team"],
            "goals_for": matches["home_score"],
            "goals_against": matches["away_score"],
        }
    )
    away = pd.DataFrame(
        {
            "source_match_no": matches["source_match_no"],
            "date": matches["date"],
            "side": "away",
            "team": matches["away_team"],
            "goals_for": matches["away_score"],
            "goals_against": matches["home_score"],
        }
    )
    team_rows = pd.concat([home, away], ignore_index=True).sort_values(["team", "date", "source_match_no"])
    team_rows["win"] = (team_rows["goals_for"] > team_rows["goals_against"]).astype(int)
    team_rows["draw"] = (team_rows["goals_for"] == team_rows["goals_against"]).astype(int)
    team_rows["loss"] = (team_rows["goals_for"] < team_rows["goals_against"]).astype(int)
    team_rows["points"] = team_rows["win"] * 3 + team_rows["draw"]
    return team_rows


def add_recent_form_features(matches: pd.DataFrame) -> pd.DataFrame:
    team_rows = build_team_perspective(matches)
    feature_rows: list[dict[str, object]] = []
    for _, team_group in team_rows.groupby("team", sort=False):
        history: deque[dict[str, float]] = deque(maxlen=10)
        team_group = team_group.sort_values(["date", "source_match_no"])
        for _, date_group in team_group.groupby("date", sort=True):
            matches_count = len(history)
            if matches_count:
                wins = sum(item["win"] for item in history)
                draws = sum(item["draw"] for item in history)
                losses = sum(item["loss"] for item in history)
                points = sum(item["points"] for item in history)
                goals_for = sum(item["goals_for"] for item in history)
                goals_against = sum(item["goals_against"] for item in history)
                features = {
                    "recent10_matches": matches_count,
                    "recent10_wins": wins,
                    "recent10_draws": draws,
                    "recent10_losses": losses,
                    "recent10_win_rate": wins / matches_count,
                    "recent10_points_per_match": points / matches_count,
                    "recent10_goals_for_avg": goals_for / matches_count,
                    "recent10_goals_against_avg": goals_against / matches_count,
                }
            else:
                features = {
                    "recent10_matches": 0,
                    "recent10_wins": 0,
                    "recent10_draws": 0,
                    "recent10_losses": 0,
                    "recent10_win_rate": pd.NA,
                    "recent10_points_per_match": pd.NA,
                    "recent10_goals_for_avg": pd.NA,
                    "recent10_goals_against_avg": pd.NA,
                }
            for row in date_group.itertuples(index=False):
                feature_rows.append({"source_match_no": row.source_match_no, "side": row.side, **features})
            for row in date_group.itertuples(index=False):
                history.append(
                    {
                        "win": row.win,
                        "draw": row.draw,
                        "loss": row.loss,
                        "points": row.points,
                        "goals_for": row.goals_for,
                        "goals_against": row.goals_against,
                    }
                )

    team_rows = pd.DataFrame(feature_rows)
    feature_cols = [
        "recent10_matches",
        "recent10_wins",
        "recent10_draws",
        "recent10_losses",
        "recent10_win_rate",
        "recent10_points_per_match",
        "recent10_goals_for_avg",
        "recent10_goals_against_avg",
    ]
    home_features = team_rows[team_rows["side"] == "home"][["source_match_no", *feature_cols]].rename(
        columns={col: f"home_{col}" for col in feature_cols}
    )
    away_features = team_rows[team_rows["side"] == "away"][["source_match_no", *feature_cols]].rename(
        columns={col: f"away_{col}" for col in feature_cols}
    )
    out = matches.merge(home_features, on="source_match_no", how="left").merge(away_features, on="source_match_no", how="left")
    return out


def add_h2h_features(matches: pd.DataFrame) -> pd.DataFrame:
    rows = matches.sort_values(["date", "source_match_no"]).copy()
    stats = defaultdict(lambda: {"matches": 0, "wins": defaultdict(int), "draws": 0, "goals": defaultdict(int), "last_date": pd.NaT})
    feature_rows: list[dict[str, object]] = []

    for match_date, date_group in rows.groupby("date", sort=True):
        for row in date_group.itertuples(index=False):
            home = row.home_team
            away = row.away_team
            key = tuple(sorted([home, away]))
            current = stats[key]
            total = current["matches"]
            if total:
                features = {
                    "source_match_no": row.source_match_no,
                    "h2h_matches": total,
                    "h2h_home_team_wins": current["wins"][home],
                    "h2h_away_team_wins": current["wins"][away],
                    "h2h_draws": current["draws"],
                    "h2h_home_team_win_rate": current["wins"][home] / total,
                    "h2h_away_team_win_rate": current["wins"][away] / total,
                    "h2h_draw_rate": current["draws"] / total,
                    "h2h_home_goals_avg": current["goals"][home] / total,
                    "h2h_away_goals_avg": current["goals"][away] / total,
                    "h2h_last_match_date": current["last_date"],
                }
            else:
                features = {
                    "source_match_no": row.source_match_no,
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
            feature_rows.append(features)

        for row in date_group.itertuples(index=False):
            home = row.home_team
            away = row.away_team
            key = tuple(sorted([home, away]))
            current = stats[key]
            current["matches"] += 1
            current["goals"][home] += row.home_score
            current["goals"][away] += row.away_score
            current["last_date"] = match_date
            if row.home_score > row.away_score:
                current["wins"][home] += 1
            elif row.home_score < row.away_score:
                current["wins"][away] += 1
            else:
                current["draws"] += 1

    h2h = pd.DataFrame(feature_rows)
    return matches.merge(h2h, on="source_match_no", how="left")


def add_labels(matches: pd.DataFrame) -> pd.DataFrame:
    out = matches.copy()
    out["result"] = "draw"
    out.loc[out["home_score"] > out["away_score"], "result"] = "home_win"
    out.loc[out["home_score"] < out["away_score"], "result"] = "away_win"
    out["home_win"] = (out["result"] == "home_win").astype(int)
    out["draw"] = (out["result"] == "draw").astype(int)
    out["away_win"] = (out["result"] == "away_win").astype(int)
    return out


def build_training_data(elo: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    training = add_labels(matches)
    training = add_elo_features(training, elo)
    training = add_recent_form_features(training)
    training = add_h2h_features(training)
    training["match_id"] = training["source_match_no"].map(lambda value: f"hist_{int(value):06d}")

    columns = [
        "match_id",
        "source_match_no",
        "date",
        "home_team",
        "away_team",
        "home_score",
        "away_score",
        "result",
        "home_win",
        "draw",
        "away_win",
        "tournament",
        "country",
        "neutral",
        "home_advantage",
        "away_advantage",
        "neutral_venue",
        "home_elo",
        "away_elo",
        "elo_diff_home_minus_away",
        "home_elo_date",
        "away_elo_date",
        "home_elo_last_change",
        "away_elo_last_change",
        "home_recent10_matches",
        "home_recent10_wins",
        "home_recent10_draws",
        "home_recent10_losses",
        "home_recent10_win_rate",
        "home_recent10_points_per_match",
        "home_recent10_goals_for_avg",
        "home_recent10_goals_against_avg",
        "away_recent10_matches",
        "away_recent10_wins",
        "away_recent10_draws",
        "away_recent10_losses",
        "away_recent10_win_rate",
        "away_recent10_points_per_match",
        "away_recent10_goals_for_avg",
        "away_recent10_goals_against_avg",
        "h2h_matches",
        "h2h_home_team_wins",
        "h2h_away_team_wins",
        "h2h_draws",
        "h2h_home_team_win_rate",
        "h2h_away_team_win_rate",
        "h2h_draw_rate",
        "h2h_home_goals_avg",
        "h2h_away_goals_avg",
        "h2h_last_match_date",
    ]
    return training[columns]


def write_report(report_path: Path, training: pd.DataFrame, elo: pd.DataFrame, matches: pd.DataFrame) -> None:
    complete_elo = training["home_elo"].notna() & training["away_elo"].notna()
    both_have_prior_form = (training["home_recent10_matches"] > 0) & (training["away_recent10_matches"] > 0)
    both_have_full_recent10 = (training["home_recent10_matches"] >= 10) & (training["away_recent10_matches"] >= 10)
    result_counts = training["result"].value_counts(dropna=False)

    lines = [
        "# 历史比赛训练数据质量报告",
        "",
        "## 总览",
        "",
        f"- 历史比赛原始行数：{len(matches)}",
        f"- 训练数据输出行数：{len(training)}",
        f"- ELO 原始行数：{len(elo)}",
        f"- 双方 ELO 都可用的比赛数：{int(complete_elo.sum())}",
        f"- 双方至少各有 1 场赛前历史状态的比赛数：{int(both_have_prior_form.sum())}",
        f"- 双方都拥有满 10 场赛前近期状态的比赛数：{int(both_have_full_recent10.sum())}",
        f"- 主胜样本数：{int(result_counts.get('home_win', 0))}",
        f"- 平局样本数：{int(result_counts.get('draw', 0))}",
        f"- 客胜样本数：{int(result_counts.get('away_win', 0))}",
        "",
        "## 数据粒度",
        "",
        "训练表的粒度是：一行 = 一场历史国家队比赛。",
        "",
        "每一行只使用该场比赛开赛前已经发生的信息生成特征，包括赛前 ELO、双方最近 10 场状态、以及赛前历史交锋。",
        "",
        "## 标签字段",
        "",
        "- `result`：三分类标签，取值为 `home_win`、`draw`、`away_win`。",
        "- `home_win`：主胜二元标签。",
        "- `draw`：平局二元标签。",
        "- `away_win`：客胜二元标签。",
        "",
        "## 注意事项",
        "",
        "- 早期比赛可能没有赛前 ELO 或近期状态，这是正常现象。",
        "- 第一场历史交锋之前，H2H 字段为空，这是正常现象。",
        "- 下一步训练模型时，可以先筛选双方 ELO 都存在、双方近期状态都存在的样本。",
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build model training data from historical international matches.")
    parser.add_argument("--elo", type=Path, default=DEFAULT_ELO)
    parser.add_argument("--matches", type=Path, default=DEFAULT_MATCHES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    elo, matches = load_sources(args.elo, args.matches)
    training = build_training_data(elo, matches)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    training.to_csv(args.output, index=False)
    write_report(args.report, training, elo, matches)
    print(f"Wrote {len(training)} rows to {args.output}")
    print(f"Wrote quality report to {args.report}")


if __name__ == "__main__":
    main()
