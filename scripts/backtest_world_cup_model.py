from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, log_loss

from train_match_result_model import (
    CLASS_ORDER,
    ELO_ONLY_FEATURE_COLUMNS,
    MODEL_VERSION,
    TARGET_COLUMN,
    V4_FEATURE_COLUMNS,
    calibrated_probabilities,
    ensemble_probabilities,
    fit_calibrator,
    fit_weighted_model,
    multiclass_brier,
    prepare_training_frame,
    probability_frame,
    sample_weights,
)


DEFAULT_TRAINING = Path("data/processed/international_match_training.csv")
DEFAULT_OUTPUT_DIR = Path("data/reports/backtests")
BACKTEST_YEARS = [2010, 2014, 2018, 2022]


def evaluate_predictions(test: pd.DataFrame, probabilities: pd.DataFrame) -> dict[str, float]:
    labels = test[TARGET_COLUMN].reset_index(drop=True)
    top1_predictions = probabilities[CLASS_ORDER].idxmax(axis=1)
    non_draw_predictions = probabilities[["home_win", "away_win"]].idxmax(axis=1)
    cm = confusion_matrix(labels, top1_predictions, labels=CLASS_ORDER)
    draw_denominator = cm[CLASS_ORDER.index("draw")].sum()
    draw_recall = cm[1, 1] / draw_denominator if draw_denominator else 0.0
    non_draw_mask = labels != "draw"
    return {
        "top1_accuracy": accuracy_score(labels, top1_predictions),
        "non_draw_pick_accuracy": accuracy_score(labels[non_draw_mask], non_draw_predictions[non_draw_mask]),
        "log_loss": log_loss(labels, probabilities[CLASS_ORDER], labels=CLASS_ORDER),
        "brier_score": multiclass_brier(labels, probabilities),
        "draw_recall": draw_recall,
        "avg_draw_prob": probabilities["draw"].mean(),
        "draw_risk_flags": int((probabilities["draw"] >= 0.24).sum()),
        "predicted_draws": int((top1_predictions == "draw").sum()),
        "actual_draws": int((labels == "draw").sum()),
    }


def calibration_rows(test: pd.DataFrame, probabilities: pd.DataFrame, year: int, model_name: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    labels = test[TARGET_COLUMN].reset_index(drop=True)

    for outcome in CLASS_ORDER:
        outcome_prob = probabilities[outcome]
        outcome_hit = (labels == outcome).astype(int)
        bins = pd.cut(outcome_prob, bins=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0], include_lowest=True)
        for interval, idx in outcome_hit.groupby(bins, observed=False).groups.items():
            if len(idx) == 0:
                continue
            index = list(idx)
            rows.append(
                {
                    "year": year,
                    "model": model_name,
                    "calibration_type": outcome,
                    "bin": str(interval),
                    "sample_count": len(index),
                    "avg_predicted_prob": outcome_prob.iloc[index].mean(),
                    "actual_rate": outcome_hit.iloc[index].mean(),
                }
            )
    return rows


def high_confidence_rows(test: pd.DataFrame, probabilities: pd.DataFrame, year: int, model_name: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    labels = test[TARGET_COLUMN].reset_index(drop=True)
    for outcome in CLASS_ORDER:
        outcome_prob = probabilities[outcome]
        outcome_hit = (labels == outcome).astype(int)
        bins = pd.cut(outcome_prob, bins=[0.7, 0.8, 0.9, 1.0], include_lowest=False)
        for interval, idx in outcome_hit.groupby(bins, observed=False).groups.items():
            if len(idx) == 0:
                continue
            index = list(idx)
            rows.append(
                {
                    "year": year,
                    "model": model_name,
                    "outcome": outcome,
                    "probability_bin": str(interval),
                    "sample_count": len(index),
                    "avg_predicted_prob": outcome_prob.iloc[index].mean(),
                    "actual_rate": outcome_hit.iloc[index].mean(),
                }
            )
    return rows


def confusion_rows(test: pd.DataFrame, probabilities: pd.DataFrame, year: int, model_name: str) -> list[dict[str, object]]:
    predictions = probabilities[CLASS_ORDER].idxmax(axis=1)
    labels = test[TARGET_COLUMN].reset_index(drop=True)
    cm = confusion_matrix(labels, predictions, labels=CLASS_ORDER)
    rows = []
    for i, actual in enumerate(CLASS_ORDER):
        for j, predicted in enumerate(CLASS_ORDER):
            rows.append({"year": year, "model": model_name, "actual": actual, "predicted": predicted, "count": int(cm[i, j])})
    return rows


def walk_forward_predict(train: pd.DataFrame, test: pd.DataFrame) -> dict[str, pd.DataFrame]:
    calibration_start = int(len(train) * 0.85)
    base_train = train.iloc[:calibration_start].copy()
    calibration_frame = train.iloc[calibration_start:].copy()
    reference_date = test["date"].min()

    v4_model = fit_weighted_model(base_train, V4_FEATURE_COLUMNS, reference_date)
    elo_model = fit_weighted_model(base_train, ELO_ONLY_FEATURE_COLUMNS, reference_date)

    v4_proba = probability_frame(v4_model.predict_proba(test[V4_FEATURE_COLUMNS]), v4_model.classes_)
    elo_proba = probability_frame(elo_model.predict_proba(test[ELO_ONLY_FEATURE_COLUMNS]), elo_model.classes_)
    raw_ensemble = (v4_proba + elo_proba) / 2

    calibration_raw = ensemble_probabilities(v4_model, elo_model, calibration_frame)
    calibrator = fit_calibrator(
        calibration_raw,
        calibration_frame[TARGET_COLUMN],
        sample_weights(calibration_frame, reference_date),
    )
    calibrated_ensemble = calibrated_probabilities(calibrator, raw_ensemble)

    return {
        "v4": v4_proba,
        "elo_only": elo_proba,
        "raw_ensemble": raw_ensemble,
        MODEL_VERSION: calibrated_ensemble,
    }


def write_markdown_report(path: Path, summary: pd.DataFrame, average_summary: pd.DataFrame, high_conf: pd.DataFrame) -> None:
    lines = [
        "# 世界杯 Walk-Forward 回测报告",
        "",
        "## 回测设置",
        "",
        "- 回测年份：2010、2014、2018、2022",
        "- 训练集：该届世界杯开赛前所有可用历史比赛",
        "- 样本权重：recency_weight × tournament_weight",
        "- 测试集：该届 `World Cup` 正赛 64 场",
        f"- 当前 active 模型：`{MODEL_VERSION}`",
        "- 对比模型：V4、Elo-only、raw ensemble、calibrated ensemble",
        "",
        "## 平均 Summary",
        "",
        average_summary.to_markdown(index=False),
        "",
        "## 分年份 Summary",
        "",
        summary.to_markdown(index=False),
        "",
        "## 高置信度概率校准",
        "",
        high_conf.to_markdown(index=False) if not high_conf.empty else "没有 70% 以上的高置信度样本。",
        "",
        "## 解读",
        "",
        "- 这里的指标是世界杯 walk-forward backtest 结果，比普通 validation 更适合作为模型版本主指标。",
        "- Log Loss 和 Brier Score 是核心概率指标。",
        "- top1 accuracy 仅辅助观察，不作为交易模型主指标。",
        "- draw 已改为风险提示，因此还需要重点看 avg_draw_prob 和 draw_risk_flags。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Walk-forward backtest current World Cup match result model.")
    parser.add_argument("--training", type=Path, default=DEFAULT_TRAINING)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--train-start", default="1990-01-01")
    parser.add_argument("--min-recent-matches", type=int, default=5)
    args = parser.parse_args()

    raw = pd.read_csv(args.training)
    raw["date"] = pd.to_datetime(raw["date"], errors="coerce")
    frame = prepare_training_frame(raw, args.train_start, args.min_recent_matches)

    summary_rows = []
    calibration = []
    high_conf = []
    confusions = []

    for year in BACKTEST_YEARS:
        test = frame[(frame["tournament"] == "World Cup") & (frame["date"].dt.year == year)].copy()
        if test.empty:
            continue
        train = frame[frame["date"] < test["date"].min()].copy()
        predictions_by_model = walk_forward_predict(train, test)

        for model_name, proba in predictions_by_model.items():
            metrics = evaluate_predictions(test, proba)
            summary_rows.append(
                {
                    "year": year,
                    "model": model_name,
                    "train_matches": len(train),
                    "test_matches": len(test),
                    **metrics,
                }
            )
            calibration.extend(calibration_rows(test, proba, year, model_name))
            high_conf.extend(high_confidence_rows(test, proba, year, model_name))
            confusions.extend(confusion_rows(test, proba, year, model_name))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary = pd.DataFrame(summary_rows)
    average_summary = (
        summary.groupby("model", as_index=False)[
            [
                "top1_accuracy",
                "non_draw_pick_accuracy",
                "log_loss",
                "brier_score",
                "draw_recall",
                "avg_draw_prob",
                "draw_risk_flags",
                "predicted_draws",
            ]
        ]
        .mean()
        .sort_values(["log_loss", "brier_score"])
    )
    calibration_df = pd.DataFrame(calibration)
    high_conf_df = pd.DataFrame(high_conf)
    confusions_df = pd.DataFrame(confusions)

    summary.to_csv(args.output_dir / "world_cup_backtest_summary.csv", index=False)
    average_summary.to_csv(args.output_dir / "world_cup_backtest_average_summary.csv", index=False)
    calibration_df.to_csv(args.output_dir / "world_cup_backtest_calibration.csv", index=False)
    high_conf_df.to_csv(args.output_dir / "world_cup_backtest_high_confidence.csv", index=False)
    confusions_df.to_csv(args.output_dir / "world_cup_backtest_confusion_matrix.csv", index=False)
    write_markdown_report(args.output_dir / "world_cup_backtest_report.zh-CN.md", summary, average_summary, high_conf_df)
    print(f"Wrote backtest outputs to {args.output_dir}")


if __name__ == "__main__":
    main()
