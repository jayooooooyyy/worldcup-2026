from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_PREDICTIONS = Path("data/processed/world_cup_2026_predictions_final.csv")
DEFAULT_TRAINING = Path("data/processed/international_match_training.csv")
DEFAULT_OUTPUT = Path("data/processed/world_cup_2026_prediction_markets.csv")
DEFAULT_ACTUALS = Path("data/actuals/world_cup_2026_actual_results.csv")

OUTCOME_COLUMNS = {
    "home_win": "home_win_prob",
    "draw": "draw_prob",
    "away_win": "away_win_prob",
}
OUTCOMES = ["home_win", "draw", "away_win"]


def probability_band(metric: str, value: float | int | None) -> str:
    if pd.isna(value):
        return "Pending"
    number = float(value)
    thresholds = {
        "high_scoring": [(0.35, "Very High"), (0.28, "High"), (0.20, "Medium")],
        "blowout": [(0.28, "Very High"), (0.20, "High"), (0.12, "Medium")],
        "team_3plus": [(0.40, "Very High"), (0.32, "High"), (0.22, "Medium")],
    }
    for cutoff, label in thresholds.get(metric, []):
        if number >= cutoff:
            return label
    return "Low"


def scoreline_pool(training: pd.DataFrame) -> pd.DataFrame:
    frame = training.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame[(frame["date"].dt.year >= 1990) & frame["result"].isin(OUTCOMES)].copy()
    frame["home_goals"] = frame["home_score"].clip(0, 5).astype(int)
    frame["away_goals"] = frame["away_score"].clip(0, 5).astype(int)
    counts = frame.groupby(["result", "home_goals", "away_goals"], as_index=False).size()
    counts["conditional_prob"] = counts["size"] / counts.groupby("result")["size"].transform("sum")
    return counts[["result", "home_goals", "away_goals", "conditional_prob"]]


def scoreline_distribution(row: pd.Series, pool: pd.DataFrame) -> pd.DataFrame:
    weights = {
        "home_win": row["home_win_prob"],
        "draw": row["draw_prob"],
        "away_win": row["away_win_prob"],
    }
    weighted = pool.copy()
    weighted["probability"] = weighted["conditional_prob"] * weighted["result"].map(weights)
    grid = (
        weighted.groupby(["home_goals", "away_goals"], as_index=False)["probability"]
        .sum()
        .sort_values("probability", ascending=False)
    )
    total = grid["probability"].sum()
    grid["probability"] = grid["probability"] / total if total else 0
    grid["scoreline"] = grid["home_goals"].astype(str) + "-" + grid["away_goals"].astype(str)
    return grid


def prediction_result_type(row: pd.Series) -> str:
    values = {outcome: row[column] for outcome, column in OUTCOME_COLUMNS.items()}
    return max(values, key=values.get)


def build_prediction_markets(predictions: pd.DataFrame, training: pd.DataFrame) -> pd.DataFrame:
    output = predictions.copy()
    pool = scoreline_pool(training)

    new_columns = {
        "prediction_result_type": pd.NA,
        "top_scoreline_1": pd.NA,
        "top_scoreline_1_prob": pd.NA,
        "top_scoreline_2": pd.NA,
        "top_scoreline_2_prob": pd.NA,
        "top_scoreline_3": pd.NA,
        "top_scoreline_3_prob": pd.NA,
        "expected_home_goals": pd.NA,
        "expected_away_goals": pd.NA,
        "over_2_5_prob": pd.NA,
        "under_2_5_prob": pd.NA,
        "both_teams_score_prob": pd.NA,
        "high_scoring_4plus_prob": pd.NA,
        "high_scoring_4plus_band": pd.NA,
        "blowout_3plus_margin_prob": pd.NA,
        "blowout_3plus_margin_band": pd.NA,
        "either_team_3plus_goals_prob": pd.NA,
        "either_team_3plus_goals_band": pd.NA,
        "first_goalscorer_pick": pd.NA,
        "first_goalscorer_prob": pd.NA,
        "goalscorer_model_status": "pending player lineup / scorer data",
        "corners_total_line": pd.NA,
        "corners_over_prob": pd.NA,
        "corners_under_prob": pd.NA,
        "first_half_corners_line": pd.NA,
        "first_half_corners_over_prob": pd.NA,
        "second_half_corners_line": pd.NA,
        "second_half_corners_over_prob": pd.NA,
        "corners_model_status": "pending corners training data",
    }
    for column, default in new_columns.items():
        output[column] = default

    known = output["home_win_prob"].notna()
    for index, row in output[known].iterrows():
        scorelines = scoreline_distribution(row, pool)
        top = scorelines.head(3).reset_index(drop=True)
        total_goals = scorelines["home_goals"] + scorelines["away_goals"]
        goal_diff = (scorelines["home_goals"] - scorelines["away_goals"]).abs()
        btts = scorelines.loc[(scorelines["home_goals"] > 0) & (scorelines["away_goals"] > 0), "probability"].sum()

        output.at[index, "prediction_result_type"] = prediction_result_type(row)
        output.at[index, "expected_home_goals"] = (scorelines["home_goals"] * scorelines["probability"]).sum()
        output.at[index, "expected_away_goals"] = (scorelines["away_goals"] * scorelines["probability"]).sum()
        output.at[index, "over_2_5_prob"] = scorelines.loc[total_goals > 2.5, "probability"].sum()
        output.at[index, "under_2_5_prob"] = scorelines.loc[total_goals <= 2.5, "probability"].sum()
        output.at[index, "both_teams_score_prob"] = btts
        high_scoring_prob = scorelines.loc[total_goals >= 4, "probability"].sum()
        blowout_prob = scorelines.loc[goal_diff >= 3, "probability"].sum()
        team_3plus_prob = scorelines.loc[
            (scorelines["home_goals"] >= 3) | (scorelines["away_goals"] >= 3),
            "probability",
        ].sum()
        output.at[index, "high_scoring_4plus_prob"] = high_scoring_prob
        output.at[index, "high_scoring_4plus_band"] = probability_band("high_scoring", high_scoring_prob)
        output.at[index, "blowout_3plus_margin_prob"] = blowout_prob
        output.at[index, "blowout_3plus_margin_band"] = probability_band("blowout", blowout_prob)
        output.at[index, "either_team_3plus_goals_prob"] = team_3plus_prob
        output.at[index, "either_team_3plus_goals_band"] = probability_band("team_3plus", team_3plus_prob)

        for rank in range(3):
            if rank >= len(top):
                continue
            output.at[index, f"top_scoreline_{rank + 1}"] = top.loc[rank, "scoreline"]
            output.at[index, f"top_scoreline_{rank + 1}_prob"] = top.loc[rank, "probability"]

    return output


def create_actuals_template(prediction_markets: pd.DataFrame, output_path: Path) -> None:
    if output_path.exists():
        return
    columns = [
        "match_id",
        "date",
        "home_team",
        "away_team",
        "status",
        "actual_home_goals",
        "actual_away_goals",
        "actual_result_type",
        "actual_first_goalscorer",
        "actual_total_corners",
        "actual_first_half_corners",
        "actual_second_half_corners",
        "source",
        "last_updated",
    ]
    template = prediction_markets[["match_id", "date", "home_team", "away_team"]].copy()
    for column in columns:
        if column not in template:
            template[column] = pd.NA
    template["status"] = "scheduled"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    template[columns].to_csv(output_path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build extended prediction market file for winner, scoreline, scorer, and corners tracking.")
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--training", type=Path, default=DEFAULT_TRAINING)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--actuals-template", type=Path, default=DEFAULT_ACTUALS)
    args = parser.parse_args()

    predictions = pd.read_csv(args.predictions)
    training = pd.read_csv(args.training)
    markets = build_prediction_markets(predictions, training)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    markets.to_csv(args.output, index=False)
    create_actuals_template(markets, args.actuals_template)
    print(f"Wrote {len(markets)} rows to {args.output}")
    print(f"Actual results template: {args.actuals_template}")


if __name__ == "__main__":
    main()
