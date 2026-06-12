from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_PREDICTIONS = Path("data/processed/world_cup_2026_prediction_markets.csv")
DEFAULT_ACTUALS = Path("data/actuals/world_cup_2026_actual_results.csv")
DEFAULT_SUMMARY = Path("data/processed/model_prediction_accuracy_summary.csv")
DEFAULT_DETAILS = Path("data/processed/model_prediction_accuracy_details.csv")


def actual_result_type(row: pd.Series) -> str | pd.NA:
    home = row.get("actual_home_goals")
    away = row.get("actual_away_goals")
    if pd.isna(home) or pd.isna(away):
        return pd.NA
    if home > away:
        return "home_win"
    if home < away:
        return "away_win"
    return "draw"


def accuracy(correct: pd.Series) -> float | pd.NA:
    valid = correct.dropna()
    return pd.NA if valid.empty else float(valid.mean())


def correct_count(correct: pd.Series) -> int:
    valid = correct.dropna()
    return int(valid.astype(bool).sum()) if not valid.empty else 0


def build_accuracy(predictions: pd.DataFrame, actuals: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    merged = predictions.merge(actuals, on=["match_id", "date", "home_team", "away_team"], how="left", suffixes=("", "_actual"))
    finished = merged["status"].astype(str).str.lower().isin(["ft", "finished", "complete", "completed", "final"])
    score_known = merged["actual_home_goals"].notna() & merged["actual_away_goals"].notna()
    evaluated = finished & score_known

    merged["actual_result_type"] = merged.apply(
        lambda row: row["actual_result_type"] if pd.notna(row.get("actual_result_type")) else actual_result_type(row),
        axis=1,
    )
    merged["predicted_exact_score"] = merged["top_scoreline_1"]
    merged["actual_exact_score"] = merged.apply(
        lambda row: f"{int(row['actual_home_goals'])}-{int(row['actual_away_goals'])}" if pd.notna(row["actual_home_goals"]) and pd.notna(row["actual_away_goals"]) else pd.NA,
        axis=1,
    )

    merged["winner_prediction_correct"] = pd.NA
    merged.loc[evaluated, "winner_prediction_correct"] = (
        merged.loc[evaluated, "prediction_result_type"] == merged.loc[evaluated, "actual_result_type"]
    )

    merged["scoreline_top1_correct"] = pd.NA
    merged.loc[evaluated, "scoreline_top1_correct"] = (
        merged.loc[evaluated, "top_scoreline_1"] == merged.loc[evaluated, "actual_exact_score"]
    )

    merged["scoreline_top3_correct"] = pd.NA
    merged.loc[evaluated, "scoreline_top3_correct"] = merged.loc[evaluated].apply(
        lambda row: row["actual_exact_score"] in {row["top_scoreline_1"], row["top_scoreline_2"], row["top_scoreline_3"]},
        axis=1,
    )

    merged["first_goalscorer_correct"] = pd.NA
    scorer_known = evaluated & merged["first_goalscorer_pick"].notna() & merged["actual_first_goalscorer"].notna()
    merged.loc[scorer_known, "first_goalscorer_correct"] = (
        merged.loc[scorer_known, "first_goalscorer_pick"].astype(str).str.lower()
        == merged.loc[scorer_known, "actual_first_goalscorer"].astype(str).str.lower()
    )

    merged["corners_total_direction_correct"] = pd.NA
    corners_known = evaluated & merged["corners_total_line"].notna() & merged["actual_total_corners"].notna()
    if corners_known.any():
        predicted_over = merged.loc[corners_known, "corners_over_prob"] >= merged.loc[corners_known, "corners_under_prob"]
        actual_over = merged.loc[corners_known, "actual_total_corners"] > merged.loc[corners_known, "corners_total_line"]
        merged.loc[corners_known, "corners_total_direction_correct"] = predicted_over.to_numpy() == actual_over.to_numpy()

    metrics = [
        {
            "metric": "winner_accuracy",
            "display_name": "赢家预测准确率",
            "evaluated_matches": int(merged["winner_prediction_correct"].dropna().shape[0]),
            "correct_predictions": correct_count(merged["winner_prediction_correct"]),
            "accuracy": accuracy(merged["winner_prediction_correct"]),
            "status": "active",
        },
        {
            "metric": "scoreline_top1_accuracy",
            "display_name": "比分预测准确率 Top 1",
            "evaluated_matches": int(merged["scoreline_top1_correct"].dropna().shape[0]),
            "correct_predictions": correct_count(merged["scoreline_top1_correct"]),
            "accuracy": accuracy(merged["scoreline_top1_correct"]),
            "status": "active",
        },
        {
            "metric": "scoreline_top3_accuracy",
            "display_name": "比分预测准确率 Top 3",
            "evaluated_matches": int(merged["scoreline_top3_correct"].dropna().shape[0]),
            "correct_predictions": correct_count(merged["scoreline_top3_correct"]),
            "accuracy": accuracy(merged["scoreline_top3_correct"]),
            "status": "active",
        },
        {
            "metric": "first_goalscorer_accuracy",
            "display_name": "进球球员预测准确率",
            "evaluated_matches": int(merged["first_goalscorer_correct"].dropna().shape[0]),
            "correct_predictions": correct_count(merged["first_goalscorer_correct"]),
            "accuracy": accuracy(merged["first_goalscorer_correct"]),
            "status": "pending scorer model/data",
        },
        {
            "metric": "corners_total_direction_accuracy",
            "display_name": "角球数量方向准确率",
            "evaluated_matches": int(merged["corners_total_direction_correct"].dropna().shape[0]),
            "correct_predictions": correct_count(merged["corners_total_direction_correct"]),
            "accuracy": accuracy(merged["corners_total_direction_correct"]),
            "status": "pending corners model/data",
        },
    ]
    summary = pd.DataFrame(metrics)
    return summary, merged


def main() -> None:
    parser = argparse.ArgumentParser(description="Update dashboard prediction accuracy from actual match results.")
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--actuals", type=Path, default=DEFAULT_ACTUALS)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--details", type=Path, default=DEFAULT_DETAILS)
    args = parser.parse_args()

    predictions = pd.read_csv(args.predictions)
    actuals = pd.read_csv(args.actuals)
    summary, details = build_accuracy(predictions, actuals)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.summary, index=False)
    details.to_csv(args.details, index=False)
    print(f"Wrote {len(summary)} summary rows to {args.summary}")
    print(f"Wrote {len(details)} detail rows to {args.details}")


if __name__ == "__main__":
    main()
