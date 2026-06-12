from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from backtest_world_cup_model import (
    BACKTEST_YEARS,
    evaluate_predictions,
    walk_forward_predict,
)
from train_match_result_model import CLASS_ORDER, MODEL_VERSION, TARGET_COLUMN, prepare_training_frame


DEFAULT_TRAINING = Path("data/processed/international_match_training.csv")
DEFAULT_OUTPUT_DIR = Path("data/reports/diagnostics")
V2_BLENDS = {
    "v2_70_30": 0.70,
    "v2_60_40": 0.60,
    "v2_50_50": 0.50,
}
PROBABILITY_FLOOR = 0.05
V3_FLOORS = {
    "v3_floor_008": 0.08,
    "v3_floor_010": 0.10,
}
V3_TEMPERATURES = {
    "v3_floor_008_T1.2": ("v3_floor_008", 1.2),
    "v3_floor_008_T1.5": ("v3_floor_008", 1.5),
    "v3_floor_010_T1.2": ("v3_floor_010", 1.2),
    "v3_floor_010_T1.5": ("v3_floor_010", 1.5),
}
V3_SUMMARY_MODELS = [
    "raw_ensemble",
    "v2_50_50",
    "v3_floor_008",
    "v3_floor_010",
    "v3_floor_008_T1.2",
    "v3_floor_008_T1.5",
    "v3_floor_010_T1.2",
    "v3_floor_010_T1.5",
]


def row_log_loss(true_label: str, probabilities: pd.Series) -> float:
    return -float(np.log(max(probabilities[true_label], 1e-15)))


def apply_probability_floor(probabilities: pd.DataFrame, floor: float = PROBABILITY_FLOOR) -> pd.DataFrame:
    floored = probabilities[CLASS_ORDER].clip(lower=floor)
    return floored.div(floored.sum(axis=1), axis=0)


def blend_probabilities(calibrated: pd.DataFrame, raw: pd.DataFrame, calibrated_weight: float) -> pd.DataFrame:
    blended = calibrated_weight * calibrated[CLASS_ORDER] + (1 - calibrated_weight) * raw[CLASS_ORDER]
    return apply_probability_floor(blended)


def temperature_scale(probabilities: pd.DataFrame, temperature: float) -> pd.DataFrame:
    clipped = probabilities[CLASS_ORDER].clip(lower=1e-12)
    scaled = np.power(clipped, 1 / temperature)
    return scaled.div(scaled.sum(axis=1), axis=0)


def match_name(row: pd.Series) -> str:
    return f"{row['home_team']} vs {row['away_team']}"


def true_class_probabilities(test: pd.DataFrame, probabilities: pd.DataFrame) -> pd.Series:
    labels = test[TARGET_COLUMN].reset_index(drop=True)
    return pd.Series(
        [probabilities.loc[idx, label] for idx, label in enumerate(labels)],
        index=probabilities.index,
    )


def extra_probability_metrics(test: pd.DataFrame, probabilities: pd.DataFrame) -> dict[str, float]:
    true_probs = true_class_probabilities(test, probabilities)
    row_losses = -np.log(true_probs.clip(lower=1e-15))
    return {
        "min_true_class_prob": float(true_probs.min()),
        "worst_10_avg_log_loss": float(row_losses.nlargest(min(10, len(row_losses))).mean()),
    }


def collect_diagnostics(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    worst_rows = []
    metrics_rows = []
    check_rows = []

    for year in BACKTEST_YEARS:
        test = frame[(frame["tournament"] == "World Cup") & (frame["date"].dt.year == year)].copy().reset_index(drop=True)
        if test.empty:
            continue
        train = frame[frame["date"] < test["date"].min()].copy()
        predictions = walk_forward_predict(train, test)
        calibrated = predictions[MODEL_VERSION].reset_index(drop=True)
        raw = predictions["raw_ensemble"].reset_index(drop=True)

        variants = {MODEL_VERSION: calibrated, "raw_ensemble": raw}
        for name, weight in V2_BLENDS.items():
            variants[name] = blend_probabilities(calibrated, raw, weight)
        for name, floor in V3_FLOORS.items():
            variants[name] = apply_probability_floor(variants["v2_50_50"], floor)
        for name, (floor_variant, temperature) in V3_TEMPERATURES.items():
            variants[name] = temperature_scale(variants[floor_variant], temperature)

        for model_name, probabilities in variants.items():
            metrics = evaluate_predictions(test, probabilities)
            metrics_rows.append({"year": year, "model": model_name, **metrics, **extra_probability_metrics(test, probabilities)})

            prob_sum = probabilities[CLASS_ORDER].sum(axis=1)
            check_rows.append(
                {
                    "year": year,
                    "model": model_name,
                    "uses_only_pre_world_cup_training_rows": bool((train["date"] < test["date"].min()).all()),
                    "calibration_rows_before_test": bool((train.iloc[int(len(train) * 0.85) :]["date"] < test["date"].min()).all()),
                    "test_rows": len(test),
                    "prob_sum_min": prob_sum.min(),
                    "prob_sum_max": prob_sum.max(),
                    "min_probability": probabilities[CLASS_ORDER].min().min(),
                    "probabilities_below_0_01": int((probabilities[CLASS_ORDER] < 0.01).sum().sum()),
                    "world_cup_knockout_rows": int(test["round"].astype(str).str.contains("Round|Quarter|Semi|Final|third", case=False, regex=True).sum())
                    if "round" in test.columns
                    else pd.NA,
                }
            )

        for idx, row in test.iterrows():
            probabilities = calibrated.loc[idx, CLASS_ORDER]
            actual = row[TARGET_COLUMN]
            worst_rows.append(
                {
                    "year": year,
                    "match": match_name(row),
                    "actual_result": actual,
                    "home_prob": probabilities["home_win"],
                    "draw_prob": probabilities["draw"],
                    "away_prob": probabilities["away_win"],
                    "true_class_prob": probabilities[actual],
                    "log_loss": row_log_loss(actual, probabilities),
                    "model_prediction": probabilities[CLASS_ORDER].idxmax(),
                }
            )

    worst = pd.DataFrame(worst_rows).sort_values("log_loss", ascending=False)
    metrics = pd.DataFrame(metrics_rows)
    checks = pd.DataFrame(check_rows)
    return worst, metrics, checks


def write_report(path: Path, worst: pd.DataFrame, metrics: pd.DataFrame, checks: pd.DataFrame) -> None:
    avg = (
        metrics.groupby("model", as_index=False)[
            [
                "top1_accuracy",
                "non_draw_pick_accuracy",
                "log_loss",
                "brier_score",
                "draw_recall",
                "avg_draw_prob",
                "draw_risk_flags",
                "predicted_draws",
                "min_true_class_prob",
                "worst_10_avg_log_loss",
            ]
        ]
        .agg(
            {
                "top1_accuracy": "mean",
                "non_draw_pick_accuracy": "mean",
                "log_loss": "mean",
                "brier_score": "mean",
                "draw_recall": "mean",
                "avg_draw_prob": "mean",
                "draw_risk_flags": "mean",
                "predicted_draws": "mean",
                "min_true_class_prob": "min",
                "worst_10_avg_log_loss": "mean",
            }
        )
        .sort_values(["log_loss", "brier_score"])
    )
    v3_summary = avg[avg["model"].isin(V3_SUMMARY_MODELS)].copy()
    lines = [
        "# Calibrated Model 诊断报告",
        "",
        "## 目的",
        "",
        "- 找出 calibrated_v1 log loss 爆炸的具体比赛。",
        "- 检查是否存在测试集泄露、概率和不为 1、极小概率、世界杯淘汰赛口径风险。",
        "- 测试更稳的 calibrated_v2 blend 版本。",
        "",
        "## Worst Log Loss Matches Top 25",
        "",
        worst.head(25).to_markdown(index=False),
        "",
        "## 平均指标",
        "",
        avg.to_markdown(index=False),
        "",
        "## Calibrated V3 Summary",
        "",
        v3_summary.to_markdown(index=False),
        "",
        "## 检查结果",
        "",
        checks.to_markdown(index=False),
        "",
        "## 结论提示",
        "",
        "- 如果 true_class_prob 极低，log loss 会被单场比赛严重拉高。",
        "- `v2_*` 版本对每个概率设置 0.05 下限并重新归一化，用于降低过度自信。",
        "- `v3_*` 版本以 `v2_50_50` 为基础，继续测试 0.08/0.10 floor 和 temperature scaling。",
        "- 淘汰赛数据口径仍需注意：历史表的 World Cup 结果可能按全场晋级结果记录，不一定全是 90 分钟三项市场口径。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose calibrated model log-loss issues and test v2 blends.")
    parser.add_argument("--training", type=Path, default=DEFAULT_TRAINING)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--train-start", default="1990-01-01")
    parser.add_argument("--min-recent-matches", type=int, default=5)
    args = parser.parse_args()

    raw = pd.read_csv(args.training)
    raw["date"] = pd.to_datetime(raw["date"], errors="coerce")
    frame = prepare_training_frame(raw, args.train_start, args.min_recent_matches)
    worst, metrics, checks = collect_diagnostics(frame)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    worst.to_csv(args.output_dir / "worst_log_loss_matches.csv", index=False)
    metrics.to_csv(args.output_dir / "calibrated_v2_metrics_by_year.csv", index=False)
    average_metrics = (
        metrics.groupby("model", as_index=False)
        .agg(
            {
                "top1_accuracy": "mean",
                "non_draw_pick_accuracy": "mean",
                "log_loss": "mean",
                "brier_score": "mean",
                "draw_recall": "mean",
                "avg_draw_prob": "mean",
                "draw_risk_flags": "mean",
                "predicted_draws": "mean",
                "min_true_class_prob": "min",
                "worst_10_avg_log_loss": "mean",
            }
        )
        .sort_values(["log_loss", "brier_score"])
    )
    average_metrics.to_csv(args.output_dir / "calibrated_v2_average_metrics.csv", index=False)
    average_metrics.loc[average_metrics["model"].isin(V3_SUMMARY_MODELS), [
        "model",
        "top1_accuracy",
        "log_loss",
        "brier_score",
        "avg_draw_prob",
        "predicted_draws",
        "draw_recall",
        "min_true_class_prob",
        "worst_10_avg_log_loss",
    ]].to_csv(args.output_dir / "calibrated_v3_summary.csv", index=False)
    checks.to_csv(args.output_dir / "calibrated_model_checks.csv", index=False)
    write_report(args.output_dir / "calibrated_model_diagnostic_report.zh-CN.md", worst, metrics, checks)
    print(f"Wrote diagnostics to {args.output_dir}")


if __name__ == "__main__":
    main()
