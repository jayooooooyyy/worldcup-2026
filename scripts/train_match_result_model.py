from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


DEFAULT_TRAINING = Path("data/processed/international_match_training.csv")
DEFAULT_BASELINE = Path("data/processed/world_cup_2026_baseline.csv")
DEFAULT_OUTPUT = Path("data/processed/world_cup_2026_baseline.csv")
DEFAULT_MODEL = Path("models/match_result_v4_elo_ensemble_calibrated.joblib")
DEFAULT_REPORT = Path("data/reports/match_result_model_v1.zh-CN.md")

V4_FEATURE_COLUMNS = [
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
]

ELO_ONLY_FEATURE_COLUMNS = [
    "home_elo",
    "away_elo",
    "elo_diff_home_minus_away",
]

FEATURE_COLUMNS = V4_FEATURE_COLUMNS
TARGET_COLUMN = "result"
CLASS_ORDER = ["home_win", "draw", "away_win"]
MODEL_VERSION = "v4_elo_ensemble_calibrated_v1"

CONTINENTAL_CHAMPIONSHIPS = {
    "African Nations Cup",
    "Asian Cup",
    "CONCACAF Championship",
    "CONCACAF Gold Cup",
    "Copa America",
    "European Championship",
    "Oceania Nations Cup",
}


def build_model() -> Pipeline:
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("model", LogisticRegression(max_iter=2000, C=0.8, random_state=42)),
        ]
    )


def prepare_training_frame(training: pd.DataFrame, train_start: str, min_recent_matches: int) -> pd.DataFrame:
    frame = training.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame[frame["date"] >= pd.Timestamp(train_start)]
    frame = frame[frame["home_elo"].notna() & frame["away_elo"].notna()]
    frame = frame[
        (frame["home_recent10_matches"] >= min_recent_matches)
        & (frame["away_recent10_matches"] >= min_recent_matches)
    ]
    frame = frame[frame[TARGET_COLUMN].isin(CLASS_ORDER)].copy()
    return frame.sort_values("date").reset_index(drop=True)


def recency_weight(match_date: pd.Timestamp, reference_date: pd.Timestamp) -> float:
    years = max((reference_date - match_date).days / 365.25, 0)
    if years <= 4:
        return 1.00
    if years <= 8:
        return 0.70
    if years <= 12:
        return 0.45
    if years <= 20:
        return 0.25
    return 0.10


def tournament_weight(tournament: object) -> float:
    name = "" if pd.isna(tournament) else str(tournament)
    if name == "World Cup":
        return 3.0
    if name in CONTINENTAL_CHAMPIONSHIPS:
        return 2.0
    if "World Cup" in name and ("qual" in name.lower() or "q" in name.lower()):
        return 1.5
    if "qualifier" in name.lower() and any(token in name for token in ["World Cup", "WC"]):
        return 1.5
    if name == "Friendly":
        return 0.5
    return 1.0


def sample_weights(frame: pd.DataFrame, reference_date: pd.Timestamp) -> pd.Series:
    dates = pd.to_datetime(frame["date"], errors="coerce")
    recency = dates.map(lambda value: recency_weight(value, reference_date))
    tournaments = frame["tournament"].map(tournament_weight)
    return recency.astype(float) * tournaments.astype(float)


def augment_swapped_matches(frame: pd.DataFrame) -> pd.DataFrame:
    swapped = frame.copy()
    swap_pairs = [
        ("home_team", "away_team"),
        ("home_score", "away_score"),
        ("home_win", "away_win"),
        ("home_elo", "away_elo"),
        ("home_elo_date", "away_elo_date"),
        ("home_elo_last_change", "away_elo_last_change"),
        ("home_recent10_matches", "away_recent10_matches"),
        ("home_recent10_wins", "away_recent10_wins"),
        ("home_recent10_draws", "away_recent10_draws"),
        ("home_recent10_losses", "away_recent10_losses"),
        ("home_recent10_win_rate", "away_recent10_win_rate"),
        ("home_recent10_points_per_match", "away_recent10_points_per_match"),
        ("home_recent10_goals_for_avg", "away_recent10_goals_for_avg"),
        ("home_recent10_goals_against_avg", "away_recent10_goals_against_avg"),
        ("h2h_home_team_wins", "h2h_away_team_wins"),
        ("h2h_home_team_win_rate", "h2h_away_team_win_rate"),
        ("h2h_home_goals_avg", "h2h_away_goals_avg"),
        ("home_advantage", "away_advantage"),
    ]
    for left, right in swap_pairs:
        if left in swapped.columns and right in swapped.columns:
            swapped[left], swapped[right] = frame[right], frame[left]
    swapped["elo_diff_home_minus_away"] = -frame["elo_diff_home_minus_away"]
    swapped[TARGET_COLUMN] = frame[TARGET_COLUMN].replace({"home_win": "away_win", "away_win": "home_win"})
    swapped["match_id"] = frame["match_id"].astype(str) + "_swapped"
    return pd.concat([frame, swapped], ignore_index=True)


def probability_frame(probabilities, classes) -> pd.DataFrame:
    proba = pd.DataFrame(probabilities, columns=classes)
    for label in CLASS_ORDER:
        if label not in proba:
            proba[label] = 0.0
    return proba[CLASS_ORDER]


def multiclass_brier(y_true: pd.Series, probabilities: pd.DataFrame) -> float:
    encoded = pd.get_dummies(y_true).reindex(columns=CLASS_ORDER, fill_value=0)
    return ((probabilities[CLASS_ORDER] - encoded[CLASS_ORDER]) ** 2).sum(axis=1).mean()


def fit_weighted_model(frame: pd.DataFrame, features: list[str], reference_date: pd.Timestamp) -> Pipeline:
    augmented = augment_swapped_matches(frame)
    weights = sample_weights(augmented, reference_date)
    model = build_model()
    model.fit(augmented[features], augmented[TARGET_COLUMN], model__sample_weight=weights)
    return model


def ensemble_probabilities(v4_model: Pipeline, elo_model: Pipeline, frame: pd.DataFrame) -> pd.DataFrame:
    v4_probs = probability_frame(v4_model.predict_proba(frame[V4_FEATURE_COLUMNS]), v4_model.classes_)
    elo_probs = probability_frame(elo_model.predict_proba(frame[ELO_ONLY_FEATURE_COLUMNS]), elo_model.classes_)
    return (v4_probs + elo_probs) / 2


def calibration_features(probabilities: pd.DataFrame) -> pd.DataFrame:
    clipped = probabilities[CLASS_ORDER].clip(1e-6, 1 - 1e-6)
    logits = np.log(clipped / (1 - clipped))
    logits.columns = [f"{col}_logit" for col in logits.columns]
    return logits


def fit_calibrator(probabilities: pd.DataFrame, labels: pd.Series, weights: pd.Series) -> LogisticRegression:
    calibrator = LogisticRegression(max_iter=2000, C=1.0, random_state=42)
    calibrator.fit(calibration_features(probabilities), labels, sample_weight=weights)
    return calibrator


def calibrated_probabilities(calibrator: LogisticRegression, probabilities: pd.DataFrame) -> pd.DataFrame:
    return probability_frame(calibrator.predict_proba(calibration_features(probabilities)), calibrator.classes_)


def draw_risk_level(draw_prob: float | pd.NA) -> str | pd.NA:
    if pd.isna(draw_prob):
        return pd.NA
    if draw_prob >= 0.30:
        return "high"
    if draw_prob >= 0.24:
        return "medium"
    return "low"


def append_predictions(
    baseline: pd.DataFrame,
    v4_model: Pipeline,
    elo_model: Pipeline,
    calibrator: LogisticRegression,
) -> tuple[pd.DataFrame, int]:
    output = baseline.copy()
    known_mask = ~output["home_is_placeholder"] & ~output["away_is_placeholder"]
    usable_mask = known_mask & output["home_elo"].notna() & output["away_elo"].notna()

    prediction_cols = [
        "home_win_prob",
        "draw_prob",
        "away_win_prob",
        "home_fair_odds",
        "draw_fair_odds",
        "away_fair_odds",
        "model_prediction",
        "predicted_winner",
        "draw_risk_level",
        "draw_risk_flag",
        "model_version",
    ]
    for col in prediction_cols:
        output[col] = pd.NA

    if usable_mask.any():
        raw = ensemble_probabilities(v4_model, elo_model, output.loc[usable_mask])
        proba = calibrated_probabilities(calibrator, raw)
        proba.index = output.loc[usable_mask].index

        output.loc[usable_mask, "home_win_prob"] = proba["home_win"]
        output.loc[usable_mask, "draw_prob"] = proba["draw"]
        output.loc[usable_mask, "away_win_prob"] = proba["away_win"]
        output.loc[usable_mask, "home_fair_odds"] = 1 / proba["home_win"]
        output.loc[usable_mask, "draw_fair_odds"] = 1 / proba["draw"]
        output.loc[usable_mask, "away_fair_odds"] = 1 / proba["away_win"]

        non_draw_pick = proba[["home_win", "away_win"]].idxmax(axis=1)
        output.loc[usable_mask, "model_prediction"] = non_draw_pick
        output.loc[usable_mask, "predicted_winner"] = np.where(
            non_draw_pick == "home_win",
            output.loc[usable_mask, "home_team"],
            output.loc[usable_mask, "away_team"],
        )
        output.loc[usable_mask, "draw_risk_level"] = proba["draw"].map(draw_risk_level)
        output.loc[usable_mask, "draw_risk_flag"] = proba["draw"] >= 0.24
        output.loc[usable_mask, "model_version"] = MODEL_VERSION

    return output, int(usable_mask.sum())


def evaluate(labels: pd.Series, probabilities: pd.DataFrame) -> dict[str, float]:
    top1_predictions = probabilities[CLASS_ORDER].idxmax(axis=1)
    non_draw_predictions = probabilities[["home_win", "away_win"]].idxmax(axis=1)
    cm = confusion_matrix(labels, top1_predictions, labels=CLASS_ORDER)
    draw_recall = cm[1, 1] / cm[1].sum() if cm[1].sum() else 0.0
    return {
        "top1_accuracy": accuracy_score(labels, top1_predictions),
        "non_draw_pick_accuracy": accuracy_score(labels[labels != "draw"], non_draw_predictions[labels != "draw"]),
        "log_loss": log_loss(labels, probabilities[CLASS_ORDER], labels=CLASS_ORDER),
        "brier_score": multiclass_brier(labels.reset_index(drop=True), probabilities.reset_index(drop=True)),
        "draw_recall": draw_recall,
        "avg_draw_prob": probabilities["draw"].mean(),
        "draw_risk_flags": int((probabilities["draw"] >= 0.24).sum()),
    }


def write_report(
    report_path: Path,
    train_frame: pd.DataFrame,
    calibration_frame: pd.DataFrame,
    validation_frame: pd.DataFrame,
    raw_metrics: dict[str, float],
    calibrated_metrics: dict[str, float],
    predicted_games: int,
    train_start: str,
    min_recent_matches: int,
) -> None:
    result_counts = train_frame[TARGET_COLUMN].value_counts()
    lines = [
        "# 第一版胜平负模型报告",
        "",
        "## 当前主模型",
        "",
        f"- 模型版本：`{MODEL_VERSION}`",
        "- 主模型：V4（Elo + recent form + goal stats）",
        "- Ensemble：V4 + Elo-only，二者概率等权平均",
        "- Calibration：使用 ensemble 概率 logits 训练 multinomial logistic calibrator",
        "- Draw 不再作为最终 pick；改为 `draw_prob` + `draw_risk_level` 风险提示",
        "",
        "## 权重",
        "",
        "- 0-4 年：1.00",
        "- 4-8 年：0.70",
        "- 8-12 年：0.45",
        "- 12-20 年：0.25",
        "- 20 年以上：0.10",
        "- World Cup：3.0",
        "- Continental Championship：2.0",
        "- World Cup Qualifier：1.5",
        "- Friendly：0.5",
        "- Other：1.0",
        "",
        "最终样本权重：`sample_weight = recency_weight * tournament_weight`",
        "",
        "## 数据量",
        "",
        f"- 训练样本起始日期：{train_start}",
        f"- 入模要求：双方 ELO 存在，双方赛前近期状态至少各有 {min_recent_matches} 场",
        f"- 入模总样本数：{len(train_frame)}",
        f"- Base model train 样本数：{int(len(train_frame) * 0.7)}",
        f"- Calibration 样本数：{len(calibration_frame)}",
        f"- Validation 样本数：{len(validation_frame)}",
        f"- 主胜样本数：{int(result_counts.get('home_win', 0))}",
        f"- 平局样本数：{int(result_counts.get('draw', 0))}",
        f"- 客胜样本数：{int(result_counts.get('away_win', 0))}",
        "",
        "## Validation 概率指标",
        "",
        "| version | top1_accuracy | non_draw_pick_accuracy | log_loss | brier_score | draw_recall | avg_draw_prob | draw_risk_flags |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        f"| raw ensemble | {raw_metrics['top1_accuracy']:.4f} | {raw_metrics['non_draw_pick_accuracy']:.4f} | {raw_metrics['log_loss']:.4f} | {raw_metrics['brier_score']:.4f} | {raw_metrics['draw_recall']:.4f} | {raw_metrics['avg_draw_prob']:.4f} | {raw_metrics['draw_risk_flags']} |",
        f"| calibrated ensemble | {calibrated_metrics['top1_accuracy']:.4f} | {calibrated_metrics['non_draw_pick_accuracy']:.4f} | {calibrated_metrics['log_loss']:.4f} | {calibrated_metrics['brier_score']:.4f} | {calibrated_metrics['draw_recall']:.4f} | {calibrated_metrics['avg_draw_prob']:.4f} | {calibrated_metrics['draw_risk_flags']} |",
        "",
        "## 世界杯预测输出",
        "",
        f"- 已写入预测概率的世界杯比赛数：{predicted_games}",
        "- 淘汰赛占位符比赛暂不预测，等待小组赛模拟后再填充球队。",
        "",
        "## 新增/更新字段",
        "",
        "- `home_win_prob`：主胜概率",
        "- `draw_prob`：平局概率，用作风险提示",
        "- `away_win_prob`：客胜概率",
        "- `model_prediction`：只在主胜/客胜中选择，不再输出 draw",
        "- `predicted_winner`：非平局方向上的预测胜者",
        "- `draw_risk_level`：`low` / `medium` / `high`",
        "- `draw_risk_flag`：平局风险是否需要提示",
        "- `model_version`：模型版本",
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train V4 + Elo-only calibrated ensemble and append World Cup probabilities.")
    parser.add_argument("--training", type=Path, default=DEFAULT_TRAINING)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--train-start", default="1990-01-01")
    parser.add_argument("--min-recent-matches", type=int, default=5)
    args = parser.parse_args()

    training = pd.read_csv(args.training)
    baseline = pd.read_csv(args.baseline)
    train_frame = prepare_training_frame(training, args.train_start, args.min_recent_matches)

    base_end = int(len(train_frame) * 0.70)
    calibration_end = int(len(train_frame) * 0.85)
    base_train = train_frame.iloc[:base_end].copy()
    calibration_frame = train_frame.iloc[base_end:calibration_end].copy()
    validation_frame = train_frame.iloc[calibration_end:].copy()

    calibration_reference = calibration_frame["date"].max()
    v4_validation_model = fit_weighted_model(base_train, V4_FEATURE_COLUMNS, calibration_reference)
    elo_validation_model = fit_weighted_model(base_train, ELO_ONLY_FEATURE_COLUMNS, calibration_reference)
    calibration_raw = ensemble_probabilities(v4_validation_model, elo_validation_model, calibration_frame)
    calibrator = fit_calibrator(
        calibration_raw,
        calibration_frame[TARGET_COLUMN],
        sample_weights(calibration_frame, calibration_reference),
    )

    validation_raw = ensemble_probabilities(v4_validation_model, elo_validation_model, validation_frame)
    validation_calibrated = calibrated_probabilities(calibrator, validation_raw)
    raw_metrics = evaluate(validation_frame[TARGET_COLUMN].reset_index(drop=True), validation_raw.reset_index(drop=True))
    calibrated_metrics = evaluate(validation_frame[TARGET_COLUMN].reset_index(drop=True), validation_calibrated.reset_index(drop=True))

    final_base_train = train_frame.iloc[:calibration_end].copy()
    final_calibration = train_frame.iloc[calibration_end:].copy()
    final_reference = final_calibration["date"].max()
    v4_model = fit_weighted_model(final_base_train, V4_FEATURE_COLUMNS, final_reference)
    elo_model = fit_weighted_model(final_base_train, ELO_ONLY_FEATURE_COLUMNS, final_reference)
    final_calibration_raw = ensemble_probabilities(v4_model, elo_model, final_calibration)
    final_calibrator = fit_calibrator(
        final_calibration_raw,
        final_calibration[TARGET_COLUMN],
        sample_weights(final_calibration, final_reference),
    )

    output, predicted_games = append_predictions(baseline, v4_model, elo_model, final_calibrator)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.model.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False)
    joblib.dump(
        {
            "v4_model": v4_model,
            "elo_model": elo_model,
            "calibrator": final_calibrator,
            "v4_features": V4_FEATURE_COLUMNS,
            "elo_features": ELO_ONLY_FEATURE_COLUMNS,
            "classes": CLASS_ORDER,
            "train_start": args.train_start,
            "min_recent_matches": args.min_recent_matches,
            "model_version": MODEL_VERSION,
        },
        args.model,
    )
    write_report(
        args.report,
        train_frame,
        calibration_frame,
        validation_frame,
        raw_metrics,
        calibrated_metrics,
        predicted_games,
        args.train_start,
        args.min_recent_matches,
    )
    print(f"Wrote predictions to {args.output}")
    print(f"Wrote model to {args.model}")
    print(f"Wrote report to {args.report}")


if __name__ == "__main__":
    main()
