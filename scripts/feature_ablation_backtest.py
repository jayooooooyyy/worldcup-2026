from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from train_match_result_model import CLASS_ORDER, TARGET_COLUMN, augment_swapped_matches, prepare_training_frame, sample_weights


DEFAULT_TRAINING = Path("data/processed/international_match_training.csv")
DEFAULT_OUTPUT_DIR = Path("data/reports/ablations")
BACKTEST_YEARS = [2010, 2014, 2018, 2022]

FEATURE_SETS = {
    "V1_elo_only": [
        "home_elo",
        "away_elo",
        "elo_diff_home_minus_away",
    ],
    "V2_elo_recent_form": [
        "home_elo",
        "away_elo",
        "elo_diff_home_minus_away",
        "home_recent10_matches",
        "home_recent10_wins",
        "home_recent10_draws",
        "home_recent10_losses",
        "home_recent10_win_rate",
        "home_recent10_points_per_match",
        "away_recent10_matches",
        "away_recent10_wins",
        "away_recent10_draws",
        "away_recent10_losses",
        "away_recent10_win_rate",
        "away_recent10_points_per_match",
    ],
    "V3_elo_recent_form_h2h": [
        "home_elo",
        "away_elo",
        "elo_diff_home_minus_away",
        "home_recent10_matches",
        "home_recent10_wins",
        "home_recent10_draws",
        "home_recent10_losses",
        "home_recent10_win_rate",
        "home_recent10_points_per_match",
        "away_recent10_matches",
        "away_recent10_wins",
        "away_recent10_draws",
        "away_recent10_losses",
        "away_recent10_win_rate",
        "away_recent10_points_per_match",
        "h2h_matches",
        "h2h_home_team_wins",
        "h2h_away_team_wins",
        "h2h_draws",
        "h2h_home_team_win_rate",
        "h2h_away_team_win_rate",
        "h2h_draw_rate",
    ],
    "V4_elo_recent_form_goal_stats": [
        "home_elo",
        "away_elo",
        "elo_diff_home_minus_away",
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
    ],
    "V5_elo_true_home_close_match": [
        "home_elo",
        "away_elo",
        "elo_diff_home_minus_away",
        "abs_elo_diff",
        "close_match",
        "home_advantage",
        "away_advantage",
        "neutral_venue",
    ],
}


def build_model() -> Pipeline:
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("model", LogisticRegression(max_iter=2000, C=0.8, random_state=42)),
        ]
    )


def add_derived_features(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["abs_elo_diff"] = out["elo_diff_home_minus_away"].abs()
    out["close_match"] = (out["abs_elo_diff"] <= 100).astype(int)
    return out


def probability_frame(probabilities, classes) -> pd.DataFrame:
    proba = pd.DataFrame(probabilities, columns=classes)
    for label in CLASS_ORDER:
        if label not in proba:
            proba[label] = 0.0
    return proba[CLASS_ORDER]


def multiclass_brier(y_true: pd.Series, probabilities: pd.DataFrame) -> float:
    encoded = pd.get_dummies(y_true).reindex(columns=CLASS_ORDER, fill_value=0)
    return ((probabilities[CLASS_ORDER] - encoded[CLASS_ORDER]) ** 2).sum(axis=1).mean()


def binary_brier(y_true_binary: pd.Series, predicted_prob: pd.Series) -> float:
    return ((predicted_prob - y_true_binary) ** 2).mean()


def evaluate(test: pd.DataFrame, probabilities: pd.DataFrame) -> dict[str, float]:
    labels = test[TARGET_COLUMN].reset_index(drop=True)
    predictions = probabilities[CLASS_ORDER].idxmax(axis=1)
    cm = confusion_matrix(labels, predictions, labels=CLASS_ORDER)
    draw_denominator = cm[CLASS_ORDER.index("draw")].sum()
    draw_recall = cm[1, 1] / draw_denominator if draw_denominator else 0.0
    correct_prob = [
        probabilities.loc[i, label]
        for i, label in enumerate(labels)
    ]
    return {
        "accuracy": accuracy_score(labels, predictions),
        "log_loss": log_loss(labels, probabilities[CLASS_ORDER], labels=CLASS_ORDER),
        "brier_score": multiclass_brier(labels, probabilities),
        "home_win_brier": binary_brier((labels == "home_win").astype(int), probabilities["home_win"]),
        "draw_brier": binary_brier((labels == "draw").astype(int), probabilities["draw"]),
        "away_win_brier": binary_brier((labels == "away_win").astype(int), probabilities["away_win"]),
        "avg_true_class_prob": sum(correct_prob) / len(correct_prob),
        "avg_draw_prob": probabilities["draw"].mean(),
        "draw_recall": draw_recall,
        "predicted_draws": int((predictions == "draw").sum()),
        "actual_draws": int((labels == "draw").sum()),
    }


def calibration_rows(test: pd.DataFrame, probabilities: pd.DataFrame, year: int, version: str) -> list[dict[str, object]]:
    rows = []
    labels = test[TARGET_COLUMN].reset_index(drop=True)
    for outcome in CLASS_ORDER:
        bins = pd.cut(probabilities[outcome], bins=[0, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1.0], include_lowest=True)
        hits = (labels == outcome).astype(int)
        for interval, idx in hits.groupby(bins, observed=False).groups.items():
            if len(idx) == 0:
                continue
            index = list(idx)
            rows.append(
                {
                    "year": year,
                    "version": version,
                    "outcome": outcome,
                    "probability_bin": str(interval),
                    "sample_count": len(index),
                    "avg_predicted_prob": probabilities[outcome].iloc[index].mean(),
                    "actual_rate": hits.iloc[index].mean(),
                }
            )
    return rows


def high_confidence_rows(test: pd.DataFrame, probabilities: pd.DataFrame, year: int, version: str) -> list[dict[str, object]]:
    rows = []
    labels = test[TARGET_COLUMN].reset_index(drop=True)
    for outcome in CLASS_ORDER:
        bins = pd.cut(probabilities[outcome], bins=[.7, .8, .9, 1.0], include_lowest=False)
        hits = (labels == outcome).astype(int)
        for interval, idx in hits.groupby(bins, observed=False).groups.items():
            if len(idx) == 0:
                continue
            index = list(idx)
            rows.append(
                {
                    "year": year,
                    "version": version,
                    "outcome": outcome,
                    "probability_bin": str(interval),
                    "sample_count": len(index),
                    "avg_predicted_prob": probabilities[outcome].iloc[index].mean(),
                    "actual_rate": hits.iloc[index].mean(),
                }
            )
    return rows


def write_report(path: Path, summary: pd.DataFrame, average_summary: pd.DataFrame, high_confidence: pd.DataFrame) -> None:
    lines = [
        "# 特征消融回测报告",
        "",
        "## 设计",
        "",
        "- V1：Elo only",
        "- V2：Elo + recent form",
        "- V3：Elo + recent form + H2H",
        "- V4：Elo + recent form + goal stats",
        "- V5：Elo + true home advantage + close match",
        "",
        "每个版本都使用 2010、2014、2018、2022 世界杯做时间回测。评估重点放在概率质量上，而不是只看 top-1 prediction。",
        "",
        "## 平均表现",
        "",
        average_summary.to_markdown(index=False),
        "",
        "## 分年份表现",
        "",
        summary.to_markdown(index=False),
        "",
        "## 高置信度校准",
        "",
        high_confidence.to_markdown(index=False) if not high_confidence.empty else "没有 70% 以上预测概率样本。",
        "",
        "## 解读建议",
        "",
        "- 优先比较 Log Loss 和 Brier Score；这两个指标更贴近交易场景中的概率质量。",
        "- Accuracy 可以保留，但不应该作为主指标。",
        "- 如果某个版本高胜率区间实际命中明显低于预测概率，需要做 calibration。",
        "- 如果 Draw recall 长期为 0，说明模型会分配平局概率，但不会把平局列为最高概率；这不一定影响交易概率使用，但需要单独监控 draw probability 的校准。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run feature ablation backtests for World Cup prediction.")
    parser.add_argument("--training", type=Path, default=DEFAULT_TRAINING)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--train-start", default="1990-01-01")
    parser.add_argument("--min-recent-matches", type=int, default=5)
    args = parser.parse_args()

    raw = pd.read_csv(args.training)
    raw["date"] = pd.to_datetime(raw["date"], errors="coerce")
    frame = add_derived_features(prepare_training_frame(raw, args.train_start, args.min_recent_matches))

    summary_rows = []
    calibration = []
    high_confidence = []

    for year in BACKTEST_YEARS:
        test = frame[(frame["tournament"] == "World Cup") & (frame["date"].dt.year == year)].copy()
        if test.empty:
            continue
        train = frame[frame["date"] < test["date"].min()].copy()
        for version, features in FEATURE_SETS.items():
            model = build_model()
            train_augmented = add_derived_features(augment_swapped_matches(train))
            weights = sample_weights(train_augmented, test["date"].min())
            model.fit(train_augmented[features], train_augmented[TARGET_COLUMN], model__sample_weight=weights)
            probabilities = probability_frame(model.predict_proba(test[features]), model.classes_)
            metrics = evaluate(test, probabilities)
            summary_rows.append(
                {
                    "year": year,
                    "version": version,
                    "train_matches": len(train),
                    "test_matches": len(test),
                    **metrics,
                }
            )
            calibration.extend(calibration_rows(test, probabilities, year, version))
            high_confidence.extend(high_confidence_rows(test, probabilities, year, version))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary = pd.DataFrame(summary_rows)
    average_summary = (
        summary.groupby("version", as_index=False)[
            [
                "accuracy",
                "log_loss",
                "brier_score",
                "home_win_brier",
                "draw_brier",
                "away_win_brier",
                "avg_true_class_prob",
                "avg_draw_prob",
                "draw_recall",
                "predicted_draws",
            ]
        ]
        .mean()
        .sort_values(["log_loss", "brier_score"])
    )
    calibration_df = pd.DataFrame(calibration)
    high_confidence_df = pd.DataFrame(high_confidence)

    summary.to_csv(args.output_dir / "feature_ablation_summary.csv", index=False)
    average_summary.to_csv(args.output_dir / "feature_ablation_average_summary.csv", index=False)
    calibration_df.to_csv(args.output_dir / "feature_ablation_calibration.csv", index=False)
    high_confidence_df.to_csv(args.output_dir / "feature_ablation_high_confidence.csv", index=False)
    write_report(args.output_dir / "feature_ablation_report.zh-CN.md", summary, average_summary, high_confidence_df)
    print(f"Wrote feature ablation outputs to {args.output_dir}")


if __name__ == "__main__":
    main()
